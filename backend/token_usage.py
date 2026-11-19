"""Aggregate provider-reported counts only. Never accept or store prompt/output text."""
from datetime import datetime, timedelta, timezone
import logging
from types import SimpleNamespace as NS

UAE = timezone(timedelta(hours=4))


def field(value, name, fallback=None):
    return value.get(name, fallback) if isinstance(value, dict) else getattr(value, name, fallback)


def integer(value):
    return value if type(value) is int and value >= 0 else None


def record(usage):
    from llm_rate_limits import request_channel
    channel = request_channel()
    if not channel:
        return
    incoming = integer(field(usage, 'input_tokens', field(usage, 'prompt_tokens')))
    outgoing = integer(field(usage, 'output_tokens', field(usage, 'completion_tokens')))
    total = integer(field(usage, 'total_tokens'))
    measured = incoming is not None and outgoing is not None
    try:
        from access_control import DATA_LOCK, load_access_data, save_access_data
        with DATA_LOCK:
            data = load_access_data()
            if channel != '__platform__' and not any(row['id'] == channel for row in data['channels']):
                return
            store = data.setdefault('token_usage', {'started_at': datetime.now(UAE).isoformat(), 'channels': {}})
            day = datetime.now(UAE).date().isoformat()
            row = store['channels'].setdefault(channel, {}).setdefault(day, {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0, 'measured_requests': 0, 'unreported_requests': 0})
            if measured:
                row['input_tokens'] += incoming
                row['output_tokens'] += outgoing
                row['total_tokens'] += total if total is not None else incoming + outgoing
                row['measured_requests'] += 1
            else:
                row['unreported_requests'] += 1
            save_access_data(data)
    except Exception as error:
        # Reporting cannot interrupt content generation or reveal provider bodies.
        logging.getLogger(__name__).warning('Token aggregate could not be recorded type=%s', type(error).__name__)


class MeteredStream:
    def __init__(self, stream):
        self.stream, self.reported = stream, False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self.reported:
            record(None)
        self.stream.close()

    def __iter__(self):
        for event in self.stream:
            if not self.reported and field(event, 'usage') is not None:
                record(field(event, 'usage'))
                self.reported = True
            yield event


class MeteredClient:
    """Legacy Azure adapter metering, including OCR and with_options children."""
    def __init__(self, sdk):
        self.sdk = sdk
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **options):
        from input_tokens import enforce
        enforce(options.get('messages', []), options.get('model', ''), response_format=options.get('response_format'))
        if options.get('stream'):
            options['stream_options'] = {'include_usage': True}
        response = self.sdk.chat.completions.create(**options)
        if options.get('stream'):
            return MeteredStream(response)
        record(field(response, 'usage'))
        return response

    def with_options(self, **options):
        return MeteredClient(self.sdk.with_options(**options))

    def close(self):
        self.sdk.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
