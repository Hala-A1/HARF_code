"""Content-free daily generation rollups and channel-scoped executive summaries."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import re

UAE = timezone(timedelta(hours=4))
GENERATION_ACTIONS = {'Copy generated', 'Bilingual copy generated', 'Bulk copy generated'}


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError, TypeError):
        return None


def format_name(value):
    value = (value or '').strip()
    return {'sms': 'SMS', 'email': 'Email', 'website': 'Website', 'google paid search': 'Google Paid Search',
            'app / push notification': 'Push notification', 'in-app message': 'In-app',
            'other': 'Other', 'single copy': 'Other', 'compliance memo': 'Compliance memo'}.get(value.lower(), value or 'Other')


def output_languages(value, fallback='unknown'):
    if isinstance(value, str):
        return Counter({fallback: 1}) if value.strip() else Counter()
    if isinstance(value, dict):
        result = Counter()
        for key, text in value.items():
            if isinstance(text, str) and text.strip():
                result['en' if key in {'en', 'english'} else 'ar' if key in {'ar', 'arabic'} else 'unknown'] += 1
        return result
    return Counter()


def add(ledger, time, channel, actor, fmt, kind, task, languages, runs):
    at = timestamp(time)
    if not at or not channel or not languages:
        return
    day = at.astimezone(UAE).date().isoformat()
    person = hashlib.sha256(str(actor).casefold().encode()).hexdigest()[:24]
    key = hashlib.sha256('|'.join([day, channel, person, fmt, kind, task]).encode()).hexdigest()
    row = ledger['buckets'].setdefault(key, dict(day=day, channel=channel, actor=person, format=fmt,
                                               type=kind, task=task, runs=0, outputs=0, languages={}))
    row['runs'] += runs
    row['outputs'] += sum(languages.values())
    for language, count in languages.items():
        row['languages'][language] = row['languages'].get(language, 0) + count


def capture(ledger, event, batches):
    meta = event.get('metadata') or {}
    if event.get('action') == 'Bulk copy generated':
        batch = next((b for b in batches if b['id'] == meta.get('batch_id')), None)
        if not batch:
            return
        for n, item in enumerate(batch.get('items', [])):
            output_id = item.get('output_id') or ''
            fmt = 'Website' if output_id.startswith('component-') else format_name(batch.get('content_channel'))
            for key, label in [('sms', 'SMS'), ('email', 'Email'), ('web', 'Website'), ('app', 'In-app'), ('push', 'Push notification')]:
                if output_id.startswith((f'b2c-{key}-', f'cx-comms-{key}-')): fmt = label
            if batch.get('channel_id') == 'security': fmt = 'Compliance memo'
            add(ledger, batch.get('created_at'), batch.get('channel_id'), batch.get('created_by_id') or batch.get('created_by_email'),
                fmt, item.get('output_name') or fmt, batch.get('task') or 'improve',
                output_languages(item.get('generated')), int(n == 0))
    elif event.get('action') in GENERATION_ACTIONS:
        lang = meta.get('output_language', 'unknown')
        if lang == 'unknown':
            match = re.search(r'\b(EN|AR)\b', event.get('detail', ''))
            if match: lang = match[1].lower()
        fmt = 'Compliance memo' if event.get('channel_id') == 'security' else format_name(meta.get('content_channel'))
        add(ledger, event.get('timestamp'), event.get('channel_id'), event.get('actor_id') or 'local:' + (event.get('actor_email') or '').casefold(),
            fmt, fmt, meta.get('task') or 'improve', output_languages(meta.get('generated'), lang), 1)


def legacy_ledger(data, exclude_batch=None):
    ledger = {'version': 1, 'started_at': datetime.now(timezone.utc).isoformat(), 'buckets': {}}
    batches = data.get('approval_batches', [])
    # Saved single copies are not a new generation. Bulk batches are authoritative;
    # their activity entries may already have fallen outside the 1,000-event log.
    for batch in batches:
        if batch.get('id') == exclude_batch or not any(e.get('action') == 'generated' for e in batch.get('events', [])):
            continue
        capture(ledger, {'action': 'Bulk copy generated', 'metadata': {'batch_id': batch['id']}}, batches)
    seen = set()
    for event in data.get('activity', []):
        if event.get('action') not in GENERATION_ACTIONS - {'Bulk copy generated'}:
            continue
        identity = (event.get('timestamp'), event.get('actor_email'), event.get('action'))
        if identity not in seen:
            capture(ledger, event, batches)
            seen.add(identity)
    return ledger


def record_generation(data, event):
    if event.get('action') not in GENERATION_ACTIONS:
        return
    if 'performance_metrics' not in data:
        data['performance_metrics'] = legacy_ledger(data, (event.get('metadata') or {}).get('batch_id'))
    capture(data['performance_metrics'], event, data.get('approval_batches', []))


def summary(data, channel, days, now=None, private=False):
    now = (now or datetime.now(timezone.utc)).astimezone(UAE)
    end = now.date() + timedelta(days=1)
    start = end - timedelta(days=days)
    previous = start - timedelta(days=days)
    ledger = data.get('performance_metrics') or legacy_ledger(data)
    rows = [r for r in ledger['buckets'].values() if r['channel'] == channel]
    current = [r for r in rows if start.isoformat() <= r['day'] < end.isoformat()]
    before = sum(r['outputs'] for r in rows if previous.isoformat() <= r['day'] < start.isoformat())
    formats, types, languages, tasks, daily = (Counter() for _ in range(5))
    for row in current:
        fmt, kind, task = row['format'], row['type'], row['task']
        if private:
            fmt = fmt if fmt in {'SMS', 'Email', 'Website', 'Google Paid Search', 'Push notification', 'In-app', 'Compliance memo', 'Other'} else 'Other'
            match = re.match(r'^(Component|Template)\s+(\d+)\b', kind, re.I)
            kind = f'{match[1].title()} {match[2]}' if match else fmt
            task = task if task in {'write', 'improve', 'review', 'translate'} else 'Other'
        formats[fmt] += row['outputs']; types[kind] += row['outputs']
        tasks[task] += row['outputs']; daily[row['day']] += row['outputs']
        languages.update(row['languages'])
    pipeline = Counter()
    for batch in ([] if private else data.get('approval_batches', [])):
        at = timestamp(batch.get('created_at'))
        if batch.get('channel_id') != channel or not at or not start <= at.astimezone(UAE).date() < end:
            continue
        status = batch.get('status', 'draft')
        pipeline['Pending review' if status.startswith('pending_') else {'approved':'Approved', 'rejected':'Rejected', 'returned_to_user':'Returned'}.get(status, 'Draft')] += 1
    total = sum(formats.values())
    ranked = lambda counter: [{'name': name, 'count': count} for name, count in counter.most_common()]
    result = dict(channel_id=channel, days=days, start=start.isoformat(), end=(end-timedelta(days=1)).isoformat(),
                generated_at=now.isoformat(), outputs=total, generation_runs=sum(r['runs'] for r in current),
                active_contributors=len({r['actor'] for r in current}), previous_outputs=before,
                change_percent=round((total-before)/before*100, 1) if before else None,
                formats=ranked(formats), types=ranked(types), languages=ranked(languages), tasks=ranked(tasks),
                daily=[{'date':(start+timedelta(days=n)).isoformat(), 'count':daily[(start+timedelta(days=n)).isoformat()]} for n in range(days)],
                approvals=ranked(pipeline), estimated_minutes_per_output=8,
                coverage_note='Counts recorded successful language outputs: English + Arabic counts as two. Saves, downloads and automatic repairs are not new outputs. Historical single-copy totals may be incomplete because the older activity log retained only 1,000 events. Daily rollups preserve new counts going forward. Approval figures describe saved batches created in this period, using their current status.')
    if private:
        result.pop('approvals')
        result['coverage_note'] = result['coverage_note'].split(' Approval figures')[0] + ' This channel summary contains aggregate counts only; content, identities and approval states are excluded.'
    return result
