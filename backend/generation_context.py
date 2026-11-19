"""Private, request-lifetime instruction snapshots, including worker threads."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import isgeneratorfunction, signature
from threading import RLock


_CURRENT = ContextVar('generation_instructions', default=None)


class GenerationContext:
    def __init__(self, channel, query):
        from inference import scope
        self.inference = scope()
        self.channel = channel
        self.query = query
        self.selections = {}
        self.general = {}
        self.lock = RLock()

    def select(self, module, path, scope, query, shared, loader):
        # A general module is selected once using the entire request, including
        # every uploaded brief. Format examples remain specific to each output.
        effective_query = self.query if shared else query
        format_id = None
        if module == 'B2B_TEMPLATES' and scope == 'website':
            from structure_retrieval import component_index_number
            format_id = component_index_number(query)
        key = (module, str(path.resolve()), None if shared else scope,
               None if shared else ('component', format_id) if format_id is not None else effective_query)
        with self.lock:
            if key not in self.selections:
                self.selections[key] = loader(effective_query)
            result = self.selections[key]
            if shared:
                self.general[key] = result[0].strip()
            return result

    def apply_general(self, prompt):
        with self.lock:
            missing = [text for text in self.general.values() if text and text not in prompt]
        return '\n\n---\n\n'.join([*missing, prompt])


def current_generation():
    return _CURRENT.get()


@contextmanager
def bind_generation(context):
    from inference import inference_scope, scope
    token = _CURRENT.set(context)
    try:
        with inference_scope(context.inference if context is not None else scope()):
            yield context
    finally:
        _CURRENT.reset(token)


def generation_request(function):
    """Reuse nested generation calls; end streaming scopes only after iteration.

    Bulk endpoints seed the query from all briefs before starting workers.
    A different business channel always receives a separate private context.
    """
    parameters = signature(function)

    def context_for(args, kwargs):
        values = parameters.bind(*args, **kwargs)
        values.apply_defaults()
        values = values.arguments
        request = values.get('request')
        channel = request.team_channel if request is not None else values.get('team_channel', 'b2b')
        existing = current_generation()
        if existing is not None and existing.channel == channel:
            return existing
        if request is not None:
            query = '\n'.join([request.instructions, request.channel, request.product_type or '',
                               *[item.text + '\n' + getattr(item, 'row_instructions', '') for item in request.items]])
        else:
            query = '\n'.join(str(values.get(key) or '') for key in
                              ('feedback', 'generated', 'instructions', 'channel'))
        return GenerationContext(channel, query)

    if isgeneratorfunction(function):
        @wraps(function)
        def streaming(*args, **kwargs):
            context = context_for(args, kwargs)
            iterator = function(*args, **kwargs)
            try:
                while True:
                    # StreamingResponse can resume each next() in a different
                    # worker context. Never leave a ContextVar token over yield.
                    with bind_generation(context):
                        try:
                            chunk = next(iterator)
                        except StopIteration:
                            return
                    yield chunk
            finally:
                with bind_generation(context):
                    iterator.close()
        return streaming

    @wraps(function)
    def wrapped(*args, **kwargs):
        with bind_generation(context_for(args, kwargs)):
            return function(*args, **kwargs)
    return wrapped
