// Convert edited, rendered copy back to the text format used by saves and exports.
// Only supported document elements are read; pasted scripts, images and styles are discarded.
export function editedCopyText(root) {
  const nestedTables = []
  function read(node, inCell = false) {
    if (node.nodeType === 3) return node.nodeValue.replace(/\u00a0/g, ' ')
    if (node.nodeType !== 1) return ''
    const tag = node.tagName.toLowerCase()
    if (['script', 'style', 'iframe', 'object', 'img', 'svg', 'noscript'].includes(tag)) return ''
    const children = () => Array.from(node.childNodes).map(child => read(child, inCell)).join('')
    if (tag === 'br') return inCell ? '<br>' : '\n'
    if (tag === 'table') {
      if (inCell) { nestedTables.push(node); return '' }
      const rows = Array.from(node.rows).filter(row => row.closest('table') === node)
        .map(row => Array.from(row.cells).flatMap(cell => {
          const value = Array.from(cell.childNodes).map(child => read(child, true)).join('').trim()
            .replace(/\r?\n/g, '<br>').replace(/(?<!\\)\|/g, '\\|')
          return [value, ...Array(Math.max(0, Math.min(cell.colSpan || 1, 30) - 1)).fill('')]
        }))
      if (!rows.length) return ''
      const width = Math.max(...rows.map(row => row.length))
      const line = row => '| ' + Array.from({ length: width }, (_, i) => row[i] || '').join(' | ') + ' |'
      return '\n\n' + [line(rows[0]), line(Array(width).fill('---')), ...rows.slice(1).map(line)].join('\n') + '\n\n'
    }
    if (node.classList.contains('copy-field')) {
      const label = node.querySelector('.copy-field-label')
      const value = Array.from(node.childNodes).filter(child => child !== label).map(child => read(child, inCell)).join('')
      return '\n\n' + (label ? label.textContent.trim() + ': ' : '') + value.trim() + '\n\n'
    }
    if (node.classList.contains('copy-section-heading')) return '\n\n[' + node.textContent.trim() + ']\n\n'
    if (tag === 'strong' || tag === 'b') return '**' + children() + '**'
    if (tag === 'em' || tag === 'i') return '*' + children() + '*'
    if (tag === 'pre') return '\n\n```text\n' + node.textContent + '\n```\n\n'
    if (tag === 'code') return '`' + children() + '`'
    if (/^h[1-6]$/.test(tag)) return '\n\n' + '#'.repeat(Number(tag[1])) + ' ' + children() + '\n\n'
    if (tag === 'li') {
      const index = Array.from(node.parentElement.children).indexOf(node) + 1
      return (node.parentElement.tagName === 'OL' ? index + '. ' : '- ') + children().trim() + '\n'
    }
    if (tag === 'ul' || tag === 'ol') return '\n\n' + children() + '\n\n'
    if (tag === 'blockquote') return '\n\n' + children().trim().split('\n').map(line => '> ' + line).join('\n') + '\n\n'
    if (tag === 'hr') return '\n\n---\n\n'
    if (tag === 'p' || tag === 'div') return (inCell ? '' : '\n') + children() + (inCell ? '<br>' : '\n')
    return children()
  }
  let text = Array.from(root.childNodes).map(node => read(node)).join('')
  // Existing Security layouts nest the recommendations table visually. Persist
  // it as its own table so the shared renderer can restore that relationship.
  for (let i = 0; i < nestedTables.length; i++) text += read(nestedTables[i])
  return text.replace(/\n{3,}/g, '\n\n').trim()
}
