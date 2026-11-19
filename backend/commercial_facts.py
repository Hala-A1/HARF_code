"""Extract explicit source tax statements without assuming a tax rate or treatment."""
import re
import unicodedata

RATE = r'(?:\d+(?:\.\d+)?\s*[%٪]\s*)?'
EXCLUDED = (rf'\b(?:excluding|exclude[sd]?|excl\.?|exclusive\s+of|not\s+(?:including|inclusive\s+of))\s*{RATE}VAT\b'
            rf'|\bVAT\s+(?:is\s+)?(?:not\s+included|excluded|exclusive)\b'
            rf'|(?:\+|\bplus)\s*{RATE}VAT\b'
            r'|(?:غير\s+شامل[ة]?|بدون|لا\s+تشمل)\s+(?:ضريبة\s+القيمة\s+المضافة|الضريبة)')
INCLUDED = (rf'\b(?:including|includes?|incl\.?|inclusive\s+of)\s*{RATE}VAT\b'
            r'|\bVAT\s+(?:is\s+)?(?:included|inclusive)\b'
            r'|شامل[ة]?\s+(?:ضريبة\s+القيمة\s+المضافة|الضريبة)')
PRICE = r'\bAED\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:درهم|دراهم)'


def normalized(text):
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', text)
    return ''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


def treatments(text):
    excluded = bool(re.search(EXCLUDED, text, re.I))
    remaining = re.sub(EXCLUDED, '', text, flags=re.I)
    included = bool(re.search(INCLUDED, remaining, re.I))
    return ({'excluded'} if excluded else set()) | ({'included'} if included else set())


def price_tax_treatment(source, value):
    """Use a single explicit treatment, or bind mixed treatments to the exact price clause."""
    source, value = normalized(source), normalized(value)
    known = treatments(source)
    if len(known) == 1:
        return next(iter(known))
    if not known:
        return None
    amounts = {((m[1] or m[2]).replace(',', '')) for m in re.finditer(PRICE, value, re.I)}
    found = set()
    for clause in re.split(r'[;\n]+|(?<!\d)\.(?!\d)', source):
        prices = {((m[1] or m[2]).replace(',', '')) for m in re.finditer(PRICE, clause, re.I)}
        if prices & amounts:
            found.update(treatments(clause))
    return next(iter(found)) if len(found) == 1 else None
