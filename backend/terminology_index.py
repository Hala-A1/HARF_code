"""Lossless, bilingual row retrieval for glossary and brand-terminology tables.

The Markdown remains authoritative. Only reference-table rows are selected;
prose rules, table headers, restrictions and company naming stay pinned.
"""
import hashlib
import re

CORE = {'etisalat', 'اتصالات', 'vat', 'ضريبة', 'aed', 'درهم'}


def variants(words):
    result = set(words)
    for word in words:
        if word.startswith('ال') and len(word) > 4:
            result.add(word[2:])
        if re.fullmatch(r'[a-z]{4,}s', word):
            result.add(word[:-1])
    return result


def cells(line):
    return [part.strip() for part in re.split(r'(?<!\\)\|', line.strip().strip('|'))]


def table_columns(header):
    columns = [re.sub(r'[^a-z]+', ' ', cell.lower()).strip() for cell in cells(header)]
    names = {'english', 'arabic', 'term', 'term phrase', 'preferred term', 'approved term',
             'approved name', 'brand name', 'product name', 'product', 'restricted term', 'do not use',
             'english term', 'arabic term', 'approved english', 'approved arabic',
             'current name', 'legacy name', 'preferred', 'restricted', 'prohibited', 'avoid', 'use instead'}
    indices = [i for i, name in enumerate(columns) if name in names or 'translation' in name]
    # Do not filter component schemas, editorial examples or arbitrary content tables.
    if not indices:
        return None
    return indices + [i for i, name in enumerate(columns) if name == 'category']


def build_index(text, tokenizer, heading=''):
    lines = text.splitlines()
    entries, postings, groups = {}, {}, {}
    active = None
    restricted_table = False
    terminology_scope = bool(re.search(r'glossary|terminology|dictionary|brand language|brand names|approved.*terms|naming', heading + '\n' + text.split('\n', 1)[0], re.I))
    for number, line in enumerate(lines):
        if not line.lstrip().startswith('|'):
            active = None
            continue
        if number + 1 < len(lines) and re.fullmatch(r'[\s|:\-]+', lines[number + 1]):
            active = table_columns(line) if terminology_scope else None
            restricted_table = bool(re.search(r'do not use|restricted|prohibited|\bavoid\b|legacy name', line, re.I))
            continue
        if active is None or re.fullmatch(r'[\s|:\-]+', line):
            continue
        values = cells(line)
        term_text = ' '.join(values[i] for i in active if i < len(values))
        # Category labels improve routing for broad briefs such as roaming.
        words = variants(tokenizer(term_text))
        pinned = bool(restricted_table or words & CORE or re.search(
            r'\b(?:do not use|restricted|prohibited|forbidden|never use|not allowed)\b|محظور|ممنوع', line, re.I))
        entry = dict(id='TERM-' + hashlib.sha256(line.encode()).hexdigest()[:12],
                     line=number + 1, text=line, pinned=pinned)
        entries[number] = entry
        primary = re.sub(r'\s+', ' ', values[active[0]].strip().casefold())
        if primary:
            groups.setdefault(primary, set()).add(number)
        for word in words:
            postings.setdefault(word, set()).add(number)
    return dict(lines=lines, entries=entries, postings=postings, groups=groups)


def select_rows(index, terms):
    selected = {number for number, entry in index['entries'].items() if entry['pinned']}
    for term in variants(terms):
        selected.update(index['postings'].get(term, ()))
    # Keep distinct senses/usage of a matched English term together, including
    # when it was found through only one of its Arabic translations.
    for group in index['groups'].values():
        if group & selected:
            selected.update(group)
    text = '\n'.join(line for number, line in enumerate(index['lines'])
                     if number not in index['entries'] or number in selected)
    return text, len(index['entries']) - len(selected), [
        {key: index['entries'][number][key] for key in ('id', 'line')}
        for number in sorted(selected)]
