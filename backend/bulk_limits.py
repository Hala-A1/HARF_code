"""Per-channel batch capacity, with a bounded application safety ceiling."""
DEFAULT_BULK_LIMIT = 20
MAX_BULK_LIMIT = 100


def channel_bulk_limit(channel):
    value = channel.get('bulk_file_limit', DEFAULT_BULK_LIMIT)
    return value if type(value) is int and 1 <= value <= MAX_BULK_LIMIT else DEFAULT_BULK_LIMIT
