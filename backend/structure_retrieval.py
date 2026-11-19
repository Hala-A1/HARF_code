"""Heading-aware retrieval: rules are pinned; only explicitly designated examples are ranked."""
import hashlib
import math
import re
import unicodedata
from collections import Counter, OrderedDict
from threading import RLock

_CACHE = OrderedDict()
_LOCK = RLock()
_STOP = set("the a an of and or to for in is with from this that your you be on as at by it are our their".split())


def tokens(text):
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = re.sub("[أإآ]", "ا", text)
    return [t for t in re.findall(r"[^\W_]+", text, re.UNICODE) if len(t) > 1 and t not in _STOP]


def sections(text):
    """Keep heading ancestry, original text, fenced blocks and source line ranges."""
    result, stack, lines, start, fenced = [], [], [], 1, False
    def emit(end):
        if lines:
            body = "".join(lines).strip()
            if body:
                result.append({"path": " > ".join(title for _, title in stack) or "Preamble",
                               "text": body, "line": start, "end_line": end,
                               "id": hashlib.sha256((str(start) + body).encode()).hexdigest()[:12]})
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        heading = None if fenced else re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            emit(number - 1)
            depth, title = len(heading[1]), heading[2]
            while stack and stack[-1][0] >= depth:
                stack.pop()
            stack.append((depth, title))
            lines, start = [], number
        lines.append(line)
    emit(len(text.splitlines()))
    return result


def invalidate_file(path):
    """Invalidate on save even when Windows reports unchanged file timestamps."""
    with _LOCK:
        _CACHE.pop(str(path.resolve()), None)


def indexed_file(path):
    path = path.resolve()
    stat = path.stat()
    signature = (stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
    key = str(path)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == signature:
            _CACHE.move_to_end(key)
            return cached[1], True
    text = path.read_text(encoding="utf-8")
    index = {"text": text, "sections": sections(text), "version": hashlib.sha256(text.encode()).hexdigest()[:16]}
    from terminology_index import build_index
    for section in index['sections']:
        section['terminology_index'] = build_index(section['text'], tokens, section['path'])
    with _LOCK:
        _CACHE[key] = (signature, index)
        _CACHE.move_to_end(key)
        while len(_CACHE) > 64:
            _CACHE.popitem(last=False)
    return index, False


def component_index_number(query):
    match = re.search(r'(?:\bcomponent|المكوّن|المكون|مكوّن|مكون)[\s-]*(?:number|no|رقم)?[\s#-]*([0-9٠-٩]+)\b', query, re.I)
    return int(match[1]) if match else None


def select_instructions(path, query, examples=False, limit=4, references=False, scope=None,
                        exact_component=None, glossary=True, template_families=None):
    index, hit = indexed_file(path)
    # A batch query can contain many briefs. Terms in the last brief must be
    # eligible for shared terminology selection just as terms in the first are.
    terms = set(tokens(query))
    query_key = (examples, references, limit, scope, exact_component, glossary, template_families, tuple(sorted(terms)))
    with _LOCK:
        prior = index.get("selections", {}).get(query_key)
        if prior:
            return prior[0], {**prior[1], "cache_hit": hit, "selection_cache_hit": True}
    mandatory, candidates, excluded_components, omitted_glossary_rows = [], [], set(), 0
    terminology_entries = []
    active_schemas = set()
    # Example N and all its nested fields remain one unit: before/after/Arabic stay together.
    scope_starts = []
    if scope is not None:
        scope_starts = index.get('line_scopes', [])
        if not scope_starts:
            current_scope = "shared"
            for line in index['text'].splitlines():
                match = re.fullmatch(r'<!-- B2B_SCOPE: ([a-z_]+) -->', line.strip())
                if match:
                    current_scope = match[1]
                scope_starts.append(current_scope)
            index['line_scopes'] = scope_starts
    for section in index["sections"]:
        if template_families is not None:
            family = re.search(r'(?:^| > )(?:B2C|CX-COMMS)-(?:EX-)?(SMS|EMAIL|WEB|APP|PUSH|UX)-', section['path'])
            if family and family[1] not in template_families:
                continue
            # Archive tables list previews of every example. The chosen example
            # bodies below already carry provenance; don't send the whole archive
            # catalogue (including other channels' sample copy) to the model.
            if re.match(r'^### BANK — ', section['text']):
                continue
        if scope is not None and scope_starts[section['line'] - 1] not in {'shared', scope}:
            continue
        if exact_component is not None:
            numbered = re.search(r'(?: > |^)(?:Component\s+|Preserved source — active component schema block\s+)(\d+)\b', section['path'], re.I)
            if numbered and int(numbered[1]) != exact_component:
                if int(numbered[1]) > 0:
                    excluded_components.add(int(numbered[1]))
                continue
            if re.search(r'Preserved source — (?:Updated - )?LLM Component Library\.docx', section['path'], re.I):
                # The updated active schema is selected above; avoid reintroducing
                # every archived component via a single preserved source block.
                continue
        schema_heading = re.match(r'^### Component\s+(\d+)\s+—', section['text'])
        if schema_heading:
            number = int(schema_heading[1])
            if number in active_schemas:
                # First active definition is authoritative. Older preserved
                # copies must not reintroduce renamed fields or obsolete limits.
                continue
            active_schemas.add(number)
        if glossary:
            from terminology_index import select_rows
            filtered, omitted, selected_terms = select_rows(section['terminology_index'], terms)
            terminology_entries.extend({**entry, 'line': section['line'] + entry['line'] - 1}
                                       for entry in selected_terms)
            if omitted:
                section = {**section, 'text': filtered}
                omitted_glossary_rows += omitted
        example_path = re.search(r"(?:^| > )((?:Example \d+|(?:B2C|CX-COMMS)-EX-[A-Z-]+-R\d+)[^>]*)(?: > |$)", section["path"], re.I)
        reference_path = re.search(r"(?:^| > )(Source page \d+[^>]*|Slide (?:EN|AR)-\d+[^>]*)(?: > |$)", section["path"], re.I)
        ranked_path = example_path if examples and example_path else reference_path if references and reference_path else None
        if ranked_path:
            group = section["path"].split(ranked_path[1])[0] + ranked_path[1]
            if candidates and candidates[-1]["path"] == group:
                candidates[-1]["text"] += "\n\n" + section["text"]
                candidates[-1]["end_line"] = section["end_line"]
            else:
                candidates.append({**section, "path": group})
        else:
            mandatory.append(section)
    stats_key = (examples, references, scope, exact_component, template_families)
    with _LOCK:
        statistics = index.get('ranking_statistics', {}).get(stats_key)
    if statistics is None:
        counts = [Counter(tokens(item["path"] + " " + item["text"])) for item in candidates]
        average = sum(sum(c.values()) for c in counts) / max(1, len(counts))
        frequencies = Counter(term for count in counts for term in count)
        statistics = (counts, average, frequencies)
        with _LOCK:
            index.setdefault('ranking_statistics', {})[stats_key] = statistics
    counts, average, frequencies = statistics
    scored = []
    for item, count in zip(candidates, counts):
        score = 0
        for term in terms:
            frequency = count[term]
            if frequency:
                idf = math.log(1 + (len(counts) - frequencies[term] + .5) / (frequencies[term] + .5))
                score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * sum(count.values()) / max(1, average)))
        if score > 0:
            scored.append((score, item))
    selected = [item for _, item in sorted(scored, key=lambda pair: (-pair[0], pair[1]["line"]))[:limit]]
    # No confident lexical match: omit optional examples, never discard rules.
    chosen = sorted(mandatory + selected, key=lambda item: item["line"])
    unique, seen = [], set()
    for item in chosen:
        # Provenance comments differ across preserved copies of the same rule.
        # Retain all copies on disk; send an identical rule only once per prompt.
        body = re.sub(r'^## Preserved source —[^\n]*\n?', '', item['text'], flags=re.M)
        body = re.sub(r'<!-- (?:PRESERVED SOURCE:|B2B_SCOPE:)[^>]*-->', '', body).strip()
        key = re.sub(r'\s+', ' ', body).strip()
        if key not in seen:
            seen.add(key)
            if body:
                unique.append({**item, 'text': body})
    text = "\n\n".join(item["text"] for item in unique)
    report = {"filename": path.name, "version": index["version"], "cache_hit": hit,
              "original_characters": len(index["text"]), "selected_characters": len(text),
              "pinned_sections": len(mandatory), "example_candidates": len(candidates),
              "selected_examples": len(selected), "sections": [{k: item[k] for k in ("id", "path", "line", "end_line")} for item in unique]}
    report.update(exact_component=exact_component, excluded_components=sorted(excluded_components),
                  omitted_glossary_rows=omitted_glossary_rows,
                  terminology_entries=terminology_entries,
                  retrieval_strategy='channel → format → exact component → shared rules → relevant terminology/examples')
    if template_families is not None:
        report['template_families'] = list(template_families)
    if references:
        report.update(reference_candidates=len(candidates), selected_references=len(selected))
    report["selection_cache_hit"] = False
    with _LOCK:
        selections = index.setdefault("selections", OrderedDict())
        selections[query_key] = (text, report)
        while len(selections) > 16:
            selections.popitem(last=False)
    return text, report


def select_b2b_templates(path, query, scope):
    """Use the file's explicit format boundaries and real section IDs for citations.

    Every matching format rule is pinned. Only preserved historical evidence and
    labelled examples are ranked; no rule is discarded by similarity search.
    """
    number = component_index_number(query) if scope == 'website' else None
    text, report = select_instructions(path, query, examples=True, references=True, scope=scope, exact_component=number)
    return text, {**report, 'format_scope': scope}


def select_b2c_templates(path, query, content_channel):
    """Route by the selected stable index; retain parent variants and dependencies."""
    explicit = re.search(r'\b(?:B2C|CX-COMMS)-(SMS|EMAIL|WEB|APP|PUSH|UX)-\d+\b', query, re.I)
    family = explicit[1].upper() if explicit else {
        'sms': 'SMS', 'email': 'EMAIL', 'website': 'WEB',
        'app / push notification': 'PUSH', 'in-app message': 'APP',
    }.get((content_channel or '').strip().lower())
    # Reviewed templates make push self-contained. Functional app/web journeys
    # inherit the indexed Digital UX guidance, not push's fixed field schema.
    families = (family, 'UX') if family in {'APP', 'WEB'} else (family,) if family else None
    return select_instructions(path, query, examples=True, template_families=families)


def document_segments(text, limit=48000):
    """Read every section, retaining ancestry; split oversized sections at line boundaries."""
    parts, current = [], ""
    for section in sections(text):
        prefix = f"Source heading: {section['path']} (starts at extracted line {section['line']})\n"
        available = limit - len(prefix)
        if available < 1000:
            prefix = prefix[:1000] + "\n"
            available = limit - len(prefix)
        body = section['text']
        while body:
            cut = min(len(body), available)
            if cut < len(body):
                boundary = body.rfind("\n", 0, cut)
                if boundary > available // 2:
                    cut = boundary + 1
            part, body = prefix + body[:cut], body[cut:]
            if current and len(current) + len(part) + 2 > limit:
                parts.append(current)
                current = ""
            current = current + "\n\n" + part if current else part
    if current:
        parts.append(current)
    return parts
