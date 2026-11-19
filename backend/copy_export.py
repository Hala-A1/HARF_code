"""Export generated copy without making another AI request."""

from io import BytesIO
from datetime import datetime
from pathlib import Path
import unicodedata
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def is_rtl(text: str) -> bool:
    for character in text:
        direction = unicodedata.bidirectional(character)
        if direction in {"R", "AL", "L"}:
            return direction in {"R", "AL"}
    return False


def create_copy_document(sections: list[dict]) -> bytes:
    document = Document()
    document.core_properties.title = "Generated copy"
    document.core_properties.author = ""
    document.core_properties.last_modified_by = ""
    for page in document.sections:
        page.page_width, page.page_height = Inches(8.27), Inches(11.69)
        page.top_margin = page.bottom_margin = Inches(0.8)
        page.left_margin = page.right_margin = Inches(0.8)
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    for level, size in [(1, 18), (2, 15), (3, 13), (4, 12), (5, 11), (6, 11)]:
        style = document.styles[f'Heading {level}']
        style.font.name = 'Arial'
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string('20242B')
        style.paragraph_format.keep_with_next = True

    metadata = next((section['metadata'] for section in sections if section.get('metadata')), None)
    if metadata:
        try:
            created_at = datetime.fromisoformat(str(metadata.get('created_at', '')).replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            created_at = 'Not recorded'
        attribution = document.add_paragraph()
        attribution.alignment = WD_ALIGN_PARAGRAPH.LEFT
        attribution.paragraph_format.keep_with_next = True
        attribution.paragraph_format.space_after = Pt(8)
        attribution.paragraph_format.line_spacing = 1
        run = attribution.add_run(f"Created by: {metadata.get('created_by') or 'Not recorded'}\nCreated at: {created_at}")
        run.font.size = Pt(8)

    logo_paragraph = document.add_paragraph()
    logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    logo_paragraph.paragraph_format.space_after = Pt(18)
    logo_paragraph.paragraph_format.keep_with_next = True
    logo_path = Path(__file__).resolve().parent.parent / "src" / "assets" / "etisalat-logo.png"
    logo_paragraph.add_run().add_picture(str(logo_path), width=Inches(1.5))

    for index, section in enumerate(sections):
        language = section.get("language", "auto")
        if index:
            divider = document.add_paragraph()
            divider.paragraph_format.space_after = Pt(12)
        score = document.add_paragraph()
        score.alignment = WD_ALIGN_PARAGRAPH.LEFT
        score.paragraph_format.keep_with_next = True
        score.add_run(f"Score: {(section.get('metadata') or {}).get('score') or 'Not evaluated'}").font.size = Pt(8)
        blocks = parse_blocks(section["text"])
        action = next((block for block in blocks if isinstance(block, list) and re.search(r"Recommended Action|الإجراء الموصى|الإجراءات الموصى", " ".join(block[0]), re.I)), None)
        target = next((row for block in blocks if isinstance(block, list) and block is not action for row in block[1:] if len(row) > 1 and re.fullmatch(r"(?:5[.\s]*)?(?:Recommendations?|التوصية|التوصيات)", row[0].replace("**", "").strip(), re.I)), None)
        for block in blocks:
            if isinstance(block, list):
                if block is action and target is not None:
                    continue
                add_table(document, block, language, target, action)
            elif isinstance(block, dict):
                paragraph = document.add_paragraph()
                add_text(paragraph, block['code'], language, code=True)
            elif block.strip():
                add_text(document.add_paragraph(), block, language)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def parse_blocks(text):
    lines = text.splitlines()
    blocks = []
    def cells(line):
        return [value.strip().replace(r"\|", "|") for value in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
    index = 0
    while index < len(lines):
        line = lines[index]
        fence = re.fullmatch(r'\s*(`{3,}|~{3,})(.*)', line)
        if fence:
            marker, content = fence[1], []
            index += 1
            while index < len(lines) and not re.fullmatch(r'\s*' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}\s*', lines[index]):
                content.append(lines[index])
                index += 1
            blocks.append({'code': '\n'.join(content)})
            index += 1
            continue
        if "|" in line and index + 1 < len(lines):
            headers, separator = cells(line), cells(lines[index + 1])
            if len(headers) == len(separator) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
                rows = [headers]
                index += 2
                while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                    rows.append(cells(lines[index]))
                    index += 1
                blocks.append(rows)
                continue
        blocks.append(line)
        index += 1
    return blocks


def add_text(paragraph, text, language, bold=False, code=False):
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    if not code:
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    markdown_heading = re.match(r"^(#{1,6})\s+(.+)$", text) if not code else None
    heading = re.fullmatch(r"\[(.+)\]", text.strip()) if not code else None
    if markdown_heading:
        paragraph.style = f'Heading {len(markdown_heading[1])}'
        text, bold = markdown_heading[2], True
    if heading:
        text = heading[1]
        bold = True
        paragraph.paragraph_format.keep_with_next = True
        paragraph.paragraph_format.space_before = Pt(12)
    if not code and not heading and not markdown_heading:
        bullet = re.match(r'^\s*[-*+]\s+(.+)$', text)
        ordered = re.match(r'^\s*(\d+)[.)]\s+(.+)$', text)
        quote = re.match(r'^>\s?(.*)$', text)
        if bullet:
            paragraph.style = 'List Bullet'
            text = bullet[1]
        elif ordered:
            # Preserve explicit numbering, including lists that restart at one.
            text = ordered[1] + '. ' + ordered[2]
            paragraph.paragraph_format.left_indent = Inches(.22)
            paragraph.paragraph_format.first_line_indent = Inches(-.22)
        elif quote:
            text = quote[1]
            paragraph.paragraph_format.left_indent = Inches(.2)
    if not code and re.fullmatch(r'\s*(?:---+|\*\*\*+)\s*', text):
        return
    rtl = language == "ar" or (language == "auto" and is_rtl(text))
    if rtl:
        properties = paragraph._p.get_or_add_pPr()
        bidi = OxmlElement('w:bidi')
        bidi.set(qn('w:val'), '1')
        properties.insert_element_before(bidi, 'w:spacing', 'w:ind', 'w:jc', 'w:rPr', 'w:sectPr')
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT if rtl else WD_ALIGN_PARAGRAPH.LEFT
    if rtl:
        # Use the paragraph's logical leading edge. Word's bidi layout mirrors
        # legacy left/right justification values; 'start' stays on the RTL edge.
        paragraph._p.pPr.find(qn('w:jc')).set(qn('w:val'), 'start')
    parts = [text] if code else re.split(r'(\*\*[^*]+\*\*|`[^`]+`|(?<!\*)\*[^*]+\*(?!\*)|(?<!\w)_[^_\n]+_(?!\w))', text)
    for part in parts:
        strong = not code and part.startswith('**') and part.endswith('**')
        italic = not code and not strong and ((part.startswith('*') and part.endswith('*')) or (part.startswith('_') and part.endswith('_')))
        mono = code or (part.startswith('`') and part.endswith('`'))
        if strong: part = part[2:-2]
        elif italic or (mono and not code): part = part[1:-1]
        run = paragraph.add_run(part)
        run.bold = bold or strong
        run.italic = italic
        if mono:
            run.font.name = 'Consolas'
            run.font.size = Pt(10)
        properties = run._r.get_or_add_rPr()
        properties.get_or_add_rFonts().set(qn("w:cs"), "Arial")
        if rtl:
            properties.append(OxmlElement("w:rtl"))


def add_table(container, rows, language, target=None, action=None):
    table = container.add_table(rows=1, cols=len(rows[0]))
    table.style = 'Table Grid'
    table.autofit = False
    available = container.width if hasattr(container, '_tc') else container.sections[-1].page_width - container.sections[-1].left_margin - container.sections[-1].right_margin
    indexed = re.fullmatch(r'(?:#|no\.?|رقم|م)', rows[0][0].replace('**', '').strip(), re.I)
    weights = [.08, .48, .20, .24] if len(rows[0]) == 4 and indexed else [.28, .72] if len(rows[0]) == 2 else [1 / len(rows[0])] * len(rows[0])
    for column, weight in zip(table.columns, weights):
        column.width = int(available * weight)
    if language == 'ar' or (language == 'auto' and is_rtl(' '.join(rows[0]))):
        table._tbl.tblPr.append(OxmlElement('w:bidiVisual'))
    header = OxmlElement('w:tblHeader')
    table.rows[0]._tr.get_or_add_trPr().append(header)
    for row_index, values in enumerate(rows):
        row = table.rows[0] if row_index == 0 else table.add_row()
        for column, cell in enumerate(row.cells):
            cell.width = int(available * weights[column])
            add_text(cell.paragraphs[0], values[column] if column < len(values) else '', language, row_index == 0)
            if row_index == 0:
                shading = OxmlElement('w:shd')
                shading.set(qn('w:fill'), 'F2EFF2')
                cell._tc.get_or_add_tcPr().append(shading)
            if values is target and column == 1 and action:
                add_table(cell, action, language)
    return table


def create_copy_workbook(sections, include_source=False):
    """One complete output per cell; keep source-system fields off the copy sheet."""
    from math import ceil
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.page import PageMargins

    workbook = Workbook()
    workbook.properties.title = "Generated copies"
    workbook.properties.creator = ""
    sheet = workbook.active
    sheet.title = "Outputs"
    sheet.append(["Output #", "Original ID", "Input", "Output", "Language", "Created by", "Created at", "Score"] if include_source else ["Output", "Language", "Generated output", "Created by", "Created at", "Score"])
    language_col, output_col, author_col, date_col = (5, 4, 6, 7) if include_source else (2, 3, 4, 5)
    references = []
    source_labels = {'__file': 'Source workbook', '__sheet': 'Worksheet', '__row': 'Source row'}

    def safe_text(value, output_number):
        text = ILLEGAL_CHARACTERS_RE.sub("", str(value if value is not None else ""))
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.encode('utf-8', errors='replace').decode('utf-8')
        if len(text.encode('utf-16-le')) // 2 > 32767:
            raise ValueError(f"Output {output_number} exceeds Excel's 32,767-character cell limit. Export this copy as Word or text to preserve the full output.")
        return text

    def write_text(cell, value, output_number, rtl=False):
        cell.value = safe_text(value, output_number)
        # Prevent source IDs, phone numbers and =formula text from being converted.
        cell.data_type = "s"
        cell.number_format = "@"
        cell.alignment = Alignment(vertical="top", horizontal="right" if rtl else "left",
                                   wrap_text=True, readingOrder=2 if rtl else 1, indent=1)

    def row_height(text, width):
        # Excel does not autofit wrapped export rows reliably. Estimate the visible
        # lines, within Excel's maximum row height; the full cell is never cut.
        lines = sum(max(1, ceil(len(line) / width)) for line in text.split("\n"))
        return min(390, max(44, 14 * lines + 14))

    for index, section in enumerate(sections, 1):
        metadata = section.get("metadata") or {}
        language = section.get("language", "auto")
        row = index + 1
        sheet.cell(row, 1, index).alignment = Alignment(vertical="top", horizontal="center")
        if include_source:
            original_id = section.get('original_id', '')
            if not original_id:
                original_id = next((value for key, value in (section.get('source_metadata') or {}).items()
                                    if re.sub(r'[^a-z0-9]', '', key.lower()) in {'replyid', 'messageid', 'recordid', 'id'}), '')
            write_text(sheet.cell(row, 2), original_id, index)
            write_text(sheet.cell(row, 3), section.get('source_text', ''), index, rtl=is_rtl(section.get('source_text', '')))
        write_text(sheet.cell(row, language_col), {"en": "English", "ar": "Arabic", "auto": "Original"}.get(language, language), index)
        write_text(sheet.cell(row, output_col), section["text"], index, rtl=language == "ar" or (language == "auto" and is_rtl(section["text"])))
        write_text(sheet.cell(row, author_col), metadata.get("created_by", ""), index)
        score_text = str(metadata.get('score') or 'Not evaluated')
        score_match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(/\s*10|%)(?:\s*\((?:partial )?AI assessment\))?', score_text)
        score_cell = sheet.cell(row, date_col + 1)
        if score_match and 0 <= float(score_match[1]) <= (100 if score_match[2] == '%' else 10):
            score_cell.value = float(score_match[1]) / (10 if score_match[2] == '%' else 1)
            score_cell.number_format = '0.0" / 10"'
            score_cell.alignment = Alignment(vertical='top', horizontal='center')
            if 'partial AI assessment' in score_text:
                score_cell.comment = Comment('Partial AI assessment: only the reviewed excerpts were assessed. This is not a full-document verification.', 'AI assessment')
        else:
            write_text(score_cell, score_text, index)
        try:
            created = datetime.fromisoformat(str(metadata.get("created_at", "")).replace("Z", "+00:00"))
            sheet.cell(row, date_col, created.replace(tzinfo=None, microsecond=0))
            sheet.cell(row, date_col).number_format = "yyyy-mm-dd hh:mm:ss"
            sheet.cell(row, date_col).alignment = Alignment(vertical="top", horizontal="left")
        except (ValueError, TypeError):
            pass
        sheet.row_dimensions[row].height = max(row_height(sheet.cell(row, output_col).value, 78), row_height(sheet.cell(row, 3).value, 61) if include_source else 0)
        for key, value in (section.get("source_metadata") or {}).items():
            if value is not None and value != "":
                references.append((index, source_labels.get(key, key), safe_text(value, index)))
        if section.get("source_text") and not include_source:
            references.append((index, "Original message", safe_text(section["source_text"], index)))

    def format_sheet(target, widths):
        target.sheet_view.showGridLines = False
        target.sheet_view.rightToLeft = False
        target.sheet_view.zoomScale = 90
        target.sheet_properties.pageSetUpPr.fitToPage = True
        target.sheet_properties.outlinePr.summaryRight = False
        target.freeze_panes = "A2"
        target.auto_filter.ref = target.dimensions
        target.sheet_properties.tabColor = "D90000" if target.title == "Outputs" else "69717D"
        for column, width in enumerate(widths, 1):
            target.column_dimensions[get_column_letter(column)].width = width
        for cell in target[1]:
            cell.font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="D90000")
            cell.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True)
        target.row_dimensions[1].height = 30
        edge = Side(style="hair", color="E1E3E8")
        for row in target.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Arial", size=11, color="20242B")
                cell.fill = PatternFill("solid", fgColor="FFFFFF" if cell.row % 2 == 0 else "F6F7F9")
                cell.border = Border(left=edge, right=edge, bottom=edge)
        target.print_title_rows = "1:1"
        target.print_area = target.dimensions
        target.page_setup.orientation = "landscape"
        target.page_setup.paperSize = target.PAPERSIZE_A4
        target.page_setup.fitToWidth = 1
        target.page_setup.fitToHeight = 0
        target.page_margins = PageMargins(left=.3, right=.3, top=.4, bottom=.4, header=.15, footer=.15)
        target.sheet_view.tabSelected = target.title == "Outputs"

    format_sheet(sheet, [9, 20, 65, 82, 12, 22, 23, 25] if include_source else [9, 12, 82, 22, 23, 25])
    if references:
        source_sheet = workbook.create_sheet("Source references")
        source_sheet.append(["Output", "Source field", "Source value"])
        for index, label, value in references:
            source_sheet.append([index, None, None])
            row = source_sheet.max_row
            source_sheet.cell(row, 1).alignment = Alignment(vertical="top", horizontal="center")
            write_text(source_sheet.cell(row, 2), label, index)
            write_text(source_sheet.cell(row, 3), value, index, rtl=is_rtl(value))
            source_sheet.row_dimensions[row].height = row_height(value, 78)
        format_sheet(source_sheet, [9, 28, 82])
    workbook.active = 0
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
