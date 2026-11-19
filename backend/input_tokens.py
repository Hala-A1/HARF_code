"""Local input-size checks for every outbound AI call. No content is persisted."""
from functools import lru_cache
import json
from pathlib import Path


class InputTokenLimitError(RuntimeError):
    code = 'input_token_limit'
    status_code = 413

    def __init__(self, count, limit, estimated=False):
        self.count, self.limit, self.estimated = count, limit, estimated
        qualifier = 'estimated ' if estimated else ''
        super().__init__(f'This AI request needs {count:,} {qualifier}input tokens; this model’s limit is {limit:,}. Shorten the brief, reduce selected context or ask the super admin to update this model’s input limit in Models & routing. Nothing was truncated or sent for this call.')


@lru_cache(maxsize=2)
def encoding(name):
    """Load bundled vocabulary files only; never fetch a tokenizer at runtime."""
    import tiktoken
    from tiktoken.load import load_tiktoken_bpe
    folder = Path(__file__).with_name('tokenizers')
    metadata = json.loads((folder / f'{name}.json').read_text(encoding='utf8'))
    return tiktoken.Encoding(name=name, pat_str=metadata['pat_str'],
                             mergeable_ranks=load_tiktoken_bpe(str(folder / f'{name}.tiktoken')),
                             special_tokens=metadata['special_tokens'])


def count_input(messages, model='', response_format=None):
    import tiktoken
    try:
        name = tiktoken.model.encoding_name_for_model(model)
        tokenizer = encoding(name) if name in {'cl100k_base', 'o200k_base'} else None
    except (KeyError, OSError, ValueError):
        tokenizer = None
    estimated = tokenizer is None
    # Allow for message roles, separators and service framing. Provider accounting
    # can differ; this preflight is separate from actual usage reporting.
    count = 64 + 12 * len(messages)

    def text_size(value):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        return len(tokenizer.encode_ordinary(text)) if tokenizer else len(text.encode('utf8'))

    for message in messages:
        for key, value in message.items():
            if key == 'content' and isinstance(value, list):
                for part in value:
                    if part.get('type') in {'image_url', 'input_image'}:
                        # Image URLs/base64 bytes are not text tokens. Reserve a
                        # conservative vision allowance per image instead.
                        count += 32768
                        estimated = True
                    else:
                        count += text_size(part)
            else:
                count += text_size(value)
    if response_format:
        count += text_size(response_format)
    return {'tokens': count, 'estimated': estimated, 'method': 'local tokenizer with framing allowance' if tokenizer else 'conservative UTF-8 byte estimate'}


def enforce(messages, model='', response_format=None, *, model_id=None, maximum=None):
    from platform_policy import settings
    config = settings()  # Re-read model overrides on every call, including pinned routes.
    if model_id:
        maximum = config['model_input_token_limits'].get(model_id, maximum or config['default_max_input_tokens'])
    elif maximum is None:
        # The legacy Azure adapter must use the limits of its actual deployment,
        # rather than a different model selected for the live gateways.
        from inference import policy
        rows = [row for row in policy()['models'] if row.get('gateway') == 'cloud' and row.get('upstream') == model]
        maximum = min(config['model_input_token_limits'].get(row['id'], row['max_input_tokens']) for row in rows) if rows else config['model_input_token_limits'].get(f'cloud:{model}', config['default_max_input_tokens'])
    result = count_input(messages, model, response_format)
    if result['tokens'] > maximum:
        raise InputTokenLimitError(result['tokens'], maximum, result['estimated'])
    return result
