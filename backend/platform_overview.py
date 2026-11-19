"""Explicit allowlist of non-content statistics for platform administration."""
from datetime import datetime, timedelta, timezone
from request_limits import RequestLimits

UAE = timezone(timedelta(hours=4))


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError, TypeError):
        return None


def summary(data, days, user, channel_id=''):
    now = datetime.now(UAE)
    since = now - timedelta(days=days)
    start_day = (now.date() - timedelta(days=days - 1)).isoformat()
    store = data.get('token_usage') or {}
    rows = []
    for channel in data['channels']:
        if channel.get('deleted_at') or (channel_id and channel['id'] != channel_id):
            continue
        members = [member for member in data['users'] if member.get('channel_id') == channel['id'] and member['role'] != 'super_admin']
        budget = RequestLimits().summary(channel['id'], [], user)
        counts = {key: 0 for key in ('input_tokens', 'output_tokens', 'total_tokens', 'measured_requests', 'unreported_requests')}
        for day, values in store.get('channels', {}).get(channel['id'], {}).items():
            if start_day <= day <= now.date().isoformat():
                for key in counts:
                    counts[key] += values.get(key, 0)
        rows.append({'id': channel['id'], 'name': channel['name'],
                     'active_users': sum(member.get('active', True) for member in members),
                     'new_users': sum(bool((created := timestamp(member.get('created_at'))) and since <= created <= now) for member in members),
                     'users_without_creation_date': sum(timestamp(member.get('created_at')) is None for member in members),
                     'monthly_requests': budget['channel_used'], 'monthly_limit': budget['channel_limit'], 'month': budget['month'],
                     'tokens': counts if counts['measured_requests'] else None,
                     'unreported_model_calls': counts['unreported_requests']})
    return {'days': days, 'timezone': 'Asia/Dubai', 'generated_at': now.isoformat(),
            'token_tracking_since': store.get('started_at'), 'channels': rows,
            'totals': {'channels': len(rows), 'active_users': sum(row['active_users'] for row in rows),
                       'new_users': sum(row['new_users'] for row in rows),
                       'monthly_requests': sum(row['monthly_requests'] for row in rows),
                       'reported_tokens': sum(row['tokens']['total_tokens'] for row in rows if row['tokens']) if any(row['tokens'] for row in rows) else None},
            'coverage_note': 'Only provider-reported token counts are measured. Earlier usage and responses without token reports are unavailable. Token counts include individual model calls, while monthly requests count user actions. New accounts use stored creation dates; imported accounts may carry their import date.'}
