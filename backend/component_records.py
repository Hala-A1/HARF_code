"""Stable component presentation owned by the app, independently of model prose."""
import re


class ComponentResponseError(ValueError):
    code = 'component_response_invalid'
    public_message = 'The AI returned an incomplete component response after automatic recovery. Please retry this component.'


FIELD_LABELS = {
    'planname': 'اسم الباقة', 'price': 'السعر', 'sticker': 'الشارة',
    'oldnewprice': 'السعر السابق والجديد', 'usps': 'المزايا', 'usp': 'الميزة',
    'tooltipnexttouspname': 'توضيح الميزة', 'moreinfocta': 'الدعوة لمزيد من المعلومات',
    'contractperiod': 'مدة العقد', 'cta': 'الدعوة لاتخاذ إجراء',
    'featuredname': 'اسم القسم', 'questionanswer': 'السؤال والإجابة',
    'question': 'السؤال', 'answer': 'الإجابة', 'image': 'الصورة', 'icon': 'الأيقونة',
    'title': 'العنوان', 'subtitle': 'العنوان الفرعي', 'description': 'الوصف',
    'heading': 'العنوان الرئيسي', 'sectionheading': 'عنوان القسم', 'pretitle': 'العنوان التمهيدي',
}

ARABIC_CTAS = {
    'buy now': 'اشتر الآن', 'apply now': 'قدّم طلبك الآن', 'learn more': 'اعرف المزيد',
    'contact sales': 'تواصل مع فريق المبيعات', 'view plans': 'استعرض الباقات',
}


def schema_fields(component):
    return [(m[1].strip(), m[2].lower() == 'mandatory') for m in re.finditer(
        r'^-\s*([^:\n]+):\s*(mandatory|optional)\b', component['definition'], re.M | re.I)]


def key(label):
    return re.sub(r'[^a-z0-9\u0600-\u06ff]', '', str(label).lower())


def record_instructions(component, bilingual=False):
    record = '{"component_name":"translated component name","cards":[{"name":"optional card heading","fields":[{"label":"exact English schema field name","value":"finished text in the requested language"}]}],"purpose":"brief purpose","source_facts":["verified fact in requested language"],"requirements":["genuine missing input only"]}'
    shape = ('{"component_name":{"english":"component name","arabic":"اسم المكوّن"},'
             '"cards":[{"name":{"english":"card heading","arabic":"عنوان البطاقة"},'
             '"fields":[{"label":"exact English schema field name",'
             '"value":{"english":"finished English text","arabic":"النص العربي النهائي"}}]}],'
             '"purpose":{"english":"brief purpose","arabic":"الغرض"},'
             '"source_facts":[{"english":"verified fact","arabic":"الحقيقة الموثّقة"}],'
             '"requirements":[{"english":"genuine missing input only","arabic":"المدخل المطلوب فقط"}]}') if bilingual else record
    focus = ''
    if component['number'] in {3, 4, 13}:
        focus = ('Each USP/benefit card communicates ONE supported benefit, not a whole rate plan. '
                 'Use concise benefit wording such as non-stop data or local minutes. '
                 'Do not repeat plan prices, contract terms and the full product name in every benefit. '
                 'Include an offer only when specifically requested and when its qualifications fit. '
                 'Otherwise keep prices and full evidence in Source facts and use non-price benefits in the short fields.')
    elif component['number'] in {11, 12}:
        focus = f"Use exactly {4 if component['number'] == 11 else 2} article cards. Mark missing article inputs instead of inventing articles."
    budgets = field_budgets(component)
    short_fields = '\n'.join(
        f'- {label}: maximum {maximum} characters INCLUDING spaces; draft target {max(1, maximum * 3 // 4)}.'
        for label, maximum in budgets.values()
    )
    return f'''
APPLICATION OUTPUT CONTRACT — this controls serialization, not writing style.
Return a JSON object with this shape, no Markdown fences or explanatory prose:
{shape}
Use the selected Component {component['number']} schema only. Include all its mandatory fields.
Include optional fields only when useful and supported. Each plan, article, question or card belongs
in its own cards entry. Keep field labels as the exact English schema names even in Arabic JSON;
the application translates these labels. Translate all VALUES and component_name naturally into
the requested language, preserving only approved names and technical tokens.
For USPs, value can be an array of objects with name and value; include the supplied USP names and
values (at least two for Rate Plan Cards). For questions use separate Question and Answer fields.
For missing facts use REQUIRED INPUT / مدخل مطلوب. For supplied assets state Supplied separately /
متوفرة بشكل منفصل. Do not invent prices, specifications, plans or article facts to fill a card.
Keep current tone-of-voice and commercial qualification rules and each field's character limit.
Do not return section markers, counts, validation verdicts, or the instruction file itself inside
field values. The application owns these elements and calculates actual counts after rendering.
The Arabic and English cards must cover the same supplied plans and benefits, independently worded.
{'Use ONE shared cards array with a bilingual value per field. Never return separate English and Arabic card arrays or repeat a card for each language.' if bilingual else ''}
{focus}
MEASURED FIELD BUDGETS (apply independently to EVERY card and EVERY language):
{short_fields}
For fields limited to 65 characters or fewer, also include an "alternatives" array alongside
"label" and "value", containing two genuinely shorter complete phrasings of the SAME benefit.
For bilingual output, each alternative is {{"english":"short English", "arabic":"عربي موجز"}}.
For single-language output, each alternative is a string in the requested language.
The application chooses a fitting alternative if the primary value exceeds its limit.
For a title limited to 25 characters or fewer use one short benefit, usually TWO words.
Do not concatenate benefits or repeat the full brief/product description in a title.
If the approved product name does not fit, keep it in a supporting field and use a concise
supported benefit as the title. Do not abbreviate approved names or remove commercial conditions.
Keep all source facts in source_facts; short benefit fields are not full-brief translations.
'''


def field_budgets(component):
    """One schema-derived budget map shared by rendering and final validation."""
    budgets = {}
    for line in component['definition'].splitlines():
        match = re.match(r'-\s*([^:]+):.*?(?:max\s+(\d+)\s+characters|(?:approximately\s+)?(\d+)\s+characters\s+max)', line, re.I)
        if match:
            label = match[1].strip()
            budgets[key(label)] = (label, int(match[2] or match[3]))
    return budgets


def split_bilingual_record(record):
    """Share card identities/labels so both languages have exactly the same structure."""
    if not isinstance(record.get('cards'), list) or not record['cards']:
        raise ComponentResponseError('Bilingual component has no cards')
    def local(value, language):
        if isinstance(value, dict):
            if 'english' in value or 'arabic' in value:
                if language not in value or value[language] is None:
                    raise ComponentResponseError('A bilingual field is missing a language')
                return local(value[language], language)
            return {key: local(item, language) for key, item in value.items()}
        if isinstance(value, list):
            return [local(item, language) for item in value]
        return value
    result = {}
    for language in ['english', 'arabic']:
        try:
            result[language] = local(record, language)
        except ComponentResponseError:
            # Preserve the other complete language; existing bounded recovery
            # regenerates only the incomplete language from the source.
            result[language] = {}
    return result


def _value(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return '; '.join(filter(None, (_value(v) for v in value)))
    if isinstance(value, dict):
        return ' — '.join(filter(None, (_value(v) for v in value.values())))
    return str(value) if isinstance(value, (int, float)) else ''


def render_record(record, component, language):
    if not isinstance(record, dict) or not isinstance(record.get('cards'), list) or not record['cards']:
        raise ComponentResponseError('Component record must contain cards and fields')
    arabic = language == 'ar'
    missing = 'مدخل مطلوب' if arabic else 'REQUIRED INPUT'
    title = _value(record.get('component_name')) or (f"المكوّن {component['number']}" if arabic else component['definition'].splitlines()[0].lstrip('# '))
    lines = ['[المحتوى الجاهز للنسخ]' if arabic else '[COPY READY CONTENT]', ('المكوّن: ' if arabic else 'Component: ') + title]
    required = schema_fields(component)
    budgets = field_budgets(component)
    for index, card in enumerate(record['cards'], 1):
        if not isinstance(card, dict) or not isinstance(card.get('fields'), list):
            raise ComponentResponseError('Component card must contain fields')
        if len(record['cards']) > 1:
            lines.extend(['', f"### {'البطاقة' if arabic else 'Card'} {index}" + (': ' + _value(card.get('name')) if card.get('name') else '')])
        fields = [dict(f) for f in card['fields'] if isinstance(f, dict) and isinstance(f.get('label'), str)]
        canonical = {key(label): label for label, _ in required}
        for field in fields:
            field_key = key(field['label'])
            translated_key = next((name for name, translated in FIELD_LABELS.items() if key(translated) == field_key), field_key)
            if translated_key == 'subtitle' and 'description' in canonical and 'subtitle' not in canonical:
                translated_key = 'description'
            elif translated_key == 'description' and 'subtitle' in canonical and 'description' not in canonical:
                translated_key = 'subtitle'
            if translated_key in canonical:
                field['label'] = canonical[translated_key]
        present = {key(f['label']) for f in fields}
        # Missing inputs remain visible instead of inventing content or aborting a batch.
        for label, mandatory in required:
            if mandatory and key(label) not in present:
                if key(label) == 'questionanswer' and {'question', 'answer'} <= present:
                    continue
                fields.append({'label': label, 'value': missing})
        if not fields:
            raise ComponentResponseError('Component card contains no schema fields')
        for field in fields:
            label, value = field['label'].strip(), _value(field.get('value')) or missing
            budget = budgets.get(key(label))
            if budget and value != missing and len(value) > budget[1]:
                # Select whole model-authored alternatives, never slice words or
                # loosen limits. Voice, localization and offer checks still run
                # on the rendered result in the generation validator.
                alternatives = field.get('alternatives')
                if isinstance(alternatives, list):
                    for alternative in alternatives:
                        if isinstance(alternative, str) and alternative.strip() and '\n' not in alternative and len(alternative.strip()) <= budget[1]:
                            value = alternative.strip()
                            break
            if arabic and 'cta' in key(label):
                value = ARABIC_CTAS.get(value.casefold(), value)
            translated = FIELD_LABELS.get(key(label), label) if arabic else label
            # Fold wrapped paragraphs into the same field so the validator counts the whole value.
            value = ' '.join(value.splitlines())
            lines.append(f'{translated}: {value}')
    lines.extend(['', '[المرجع والتحقق]' if arabic else '[REFERENCE AND VALIDATION]'])
    purpose = _value(record.get('purpose'))
    if purpose:
        lines.append(('الغرض: ' if arabic else 'Purpose: ') + purpose)
    lines.append('عدد الأحرف:' if arabic else 'Character counts:')
    lines.append('الحقائق المصدرية:' if arabic else 'Source facts:')
    for fact in record.get('source_facts', []) if isinstance(record.get('source_facts'), list) else []:
        if _value(fact):
            lines.append('- ' + ' '.join(_value(fact).splitlines()))
    lines.append('المتطلبات:' if arabic else 'Requirements:')
    for requirement in record.get('requirements', []) if isinstance(record.get('requirements'), list) else []:
        if _value(requirement):
            lines.append('- ' + ' '.join(_value(requirement).splitlines()))
    lines.append('التحقق العام: مدخل مطلوب' if arabic else 'Overall validation: REQUIRED INPUT')
    return '\n'.join(lines)
