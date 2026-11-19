"""Local, lossless text extraction for multilingual Word and text briefs."""
import io
from zipfile import ZipFile
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def decode_text(content):
    if content.startswith((b'\xff\xfe', b'\xfe\xff')):
        return content.decode('utf-16').strip()
    # Never replace undecodable Arabic bytes with silent replacement characters.
    return content.decode('utf-8-sig').strip()


def word_text(content):
    with ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        parts = ['word/document.xml'] + sorted(
            n for n in names if n.startswith(('word/header', 'word/footer')) and n.endswith('.xml'))
        parts += [n for n in ('word/footnotes.xml', 'word/endnotes.xml') if n in names]
        output = []
        for name in parts:
            root = ET.fromstring(archive.read(name))
            # Each text node appears exactly once, including nested tables,
            # hyperlinks, content controls and text boxes. Deleted revisions
            # use delText and are intentionally excluded.
            tokens = []
            def visit(node):
                if node.tag == W + 'del':
                    return
                if node.tag == W + 't':
                    tokens.append(node.text or '')
                elif node.tag == W + 'tab':
                    tokens.append('\t')
                elif node.tag in (W + 'br', W + 'cr'):
                    tokens.append('\n')
                for child in node:
                    visit(child)
                if node.tag in (W + 'p', W + 'tr'):
                    tokens.append('\n')
                elif node.tag == W + 'tc':
                    tokens.append('\t')
            visit(root)
            text = ''.join(tokens).strip()
            if text:
                output.append(text)
        return '\n\n'.join(output)
