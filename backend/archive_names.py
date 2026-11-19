"""Short archive labels derived locally from existing copy, without AI requests."""
import re


def clean(value, maximum=52):
    value = re.sub(r'<[^>]*>', '', str(value or ''))
    value = re.sub(r'[*#\[\]`_|]+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip(' .—-:')
    if len(value) > maximum:
        shortened = value[:maximum-1]
        if ' ' in shortened: shortened = shortened.rsplit(' ', 1)[0]
        value = shortened.rstrip(' .—-:') + '…'
    return value


def useful(value):
    text = clean(value)
    return bool(text and not re.fullmatch(r'(?:unknown|not specified|generated copy.*|compliance memo|test\w*|brief|document|source|input|copy|review|write|improve|translate|(?:file|upload|email|sms)[ _-]*\d+|\d+-file copy batch|component\s*\d+.*|template\s*\d+.*)', text, re.I)
                and not re.fullmatch(r'[a-f0-9-]{24,}', text, re.I))


def topic_for(batch, item):
    # Prefer the actual output subject/title; avoid validation and instruction headings.
    generated = item.get('generated') or {}
    text = str(generated.get('en') or generated.get('ar') or next(iter(generated.values()), '') or '')
    match = re.search(r'^\s*(?:\*\*)?(?:Subject|Title|Memo subject|الموضوع|العنوان)(?:\*\*)?\s*[:：]\s*(.+)', text, re.I | re.M)
    if match and useful(match[1]): return clean(match[1])
    for value in [batch.get('product_type'), batch.get('title')]:
        if useful(value): return clean(value)
    # Plain SMS/email outputs may have no labelled title. Use a real opening line.
    for line in text.splitlines():
        if not re.search(r'COPY READY|REFERENCE|VALIDATION|CHARACTER|SOURCE FACTS|^\s*(?:Component|Template|Purpose|Requirements?|Overall|Score|المكوّن|المكون|التحقق|المراجع)\b|^\s*[|\[]', line, re.I) and useful(line) and len(clean(line)) >= 10:
            return clean(line)
    filename = re.sub(r'\.(?:docx?|pdf|txt|md|csv|json)$', '', item.get('source_filename') or item.get('filename', ''), flags=re.I)
    if useful(filename): return clean(filename)
    for line in (item.get('source') or '').splitlines():
        if useful(line) and len(clean(line)) >= 8: return clean(line)
    return 'Compliance memo' if batch.get('channel_id') == 'security' else 'Writing draft'


def ensure_archive_names(batch):
    changed = False
    for item in batch.get('items', []):
        if not item.get('archive_name'):
            topic = topic_for(batch, item)
            format_name = item.get('output_name') if item.get('output_id') else batch.get('content_channel', '')
            format_name = re.sub(r'^Component\s+(\d+)\s*[—-]\s*', r'C\1 · ', format_name or '', flags=re.I)
            format_name = clean(format_name, 30)
            suffix = f' — {format_name}' if format_name and format_name.lower() not in {'unknown', 'other', 'single copy', topic.lower()} else ''
            item['archive_name'] = clean(topic + suffix, 78)
            changed = True
    if not batch.get('archive_name'):
        items = batch.get('items', [])
        topic = topic_for(batch, items[0]) if items else clean(batch.get('title')) or 'Writing draft'
        batch['archive_name'] = items[0]['archive_name'] if len(items) == 1 else clean(f'{topic} — {len(items)} copies', 78)
        changed = True
    return changed
