import { markdownToHtml } from './markdown.js'

export function formattedCopyHtml(text) {
  const html = markdownToHtml(text)
  const document = new DOMParser().parseFromString(html, 'text/html')
  const tables = Array.from(document.querySelectorAll('table'))
  const actions = tables.find((table) => {
    const headings = table.querySelector('thead')?.textContent || ''
    return /Recommended Action/i.test(headings) || /الإجراء الموصى|الإجراءات الموصى/.test(headings)
  })
  if (actions) {
    if (actions.rows[0]?.cells.length === 4 && /^(?:#|no\.?|رقم|م)$/i.test(actions.rows[0].cells[0].textContent.trim())) {
      const columns = document.createElement('colgroup')
      for (const width of [8, 48, 20, 24]) {
        const column = document.createElement('col')
        column.style.width = `${width}%`
        columns.appendChild(column)
      }
      actions.prepend(columns)
    }
    const recommendation = tables.filter((table) => table !== actions)
      .flatMap((table) => Array.from(table.querySelectorAll('tbody > tr')))
      .find((row) => /^(?:5[.\s]*)?(?:Recommendation(?:s)?|التوصية|التوصيات)\s*$/i.test(row.cells[0]?.textContent.trim() || ''))
    if (recommendation?.cells[1]) {
      const wrapper = actions.parentElement
      recommendation.cells[1].appendChild(actions)
      if (wrapper?.classList.contains('markdown-table-wrap')) wrapper.remove()
    }
  }
  const componentCopy = /COPY READY CONTENT|المحتوى الجاهز للنسخ/.test(text)
  for (const paragraph of componentCopy ? document.querySelectorAll('body > p') : []) {
    const value = paragraph.textContent.trim()
    if (/^\[.+\]$/.test(value)) {
      const heading = document.createElement('h3')
      heading.className = 'copy-section-heading'
      heading.textContent = value.slice(1, -1)
      paragraph.replaceWith(heading)
    } else if (/^([^:]{1,55}):\s*(.*)$/.test(value)) {
      const match = value.match(/^([^:]{1,55}):\s*(.*)$/)
      const label = document.createElement('strong')
      label.className = 'copy-field-label'
      label.textContent = match[1]
      const content = document.createElement('span')
      content.textContent = match[2]
      paragraph.className = 'copy-field'
      paragraph.replaceChildren(label, content)
    }
  }
  return document.body.innerHTML
}


export function formattedCopyText(text, { tables = 'grid' } = {}) {
  const doc = new DOMParser().parseFromString(formattedCopyHtml(text), 'text/html')
  function tableText(table) {
    if (tables === 'records') {
      const rows = Array.from(table.rows)
      const headers = Array.from(rows[0]?.cells || []).map(cell => cell.textContent.trim())
      return rows.slice(1).map(row => Array.from(row.cells).map((cell, i) => {
        const clone = cell.cloneNode(true)
        for (const br of clone.querySelectorAll('br')) br.replaceWith(doc.createTextNode('\n'))
        for (const nested of clone.querySelectorAll('table')) nested.replaceWith(doc.createTextNode('\n' + tableText(nested)))
        return `${headers[i] || ''}: ${clone.textContent.trim()}`
      }).join('\n')).join('\n\n')
    }
    const rows = Array.from(table.rows).map(row => Array.from(row.cells).map(cell => {
      const clone = cell.cloneNode(true)
      const hasNested = Boolean(clone.querySelector('table'))
      for (const br of clone.querySelectorAll('br')) br.replaceWith(doc.createTextNode('\n'))
      for (const nested of clone.querySelectorAll('table')) nested.replaceWith(doc.createTextNode('\n' + tableText(nested) + '\n'))
      const lines = clone.textContent.trim().split('\n')
      return hasNested ? lines : lines.flatMap(line => line.match(/.{1,52}(?:\s|$)|.{1,52}/gu)?.map(part => part.trimEnd()) || [''])
    }))
    const columns = Math.max(...rows.map(row => row.length))
    const widths = Array.from({ length: columns }, (_, i) => Math.max(3, ...rows.flatMap(row => (row[i] || ['']).map(line => line.length))))
    const border = '+' + widths.map(width => '-'.repeat(width + 2)).join('+') + '+'
    return [border, ...rows.flatMap(row => {
      const height = Math.max(...row.map(cell => cell.length))
      return [...Array.from({ length: height }, (_, index) => '| ' + widths.map((width, col) => (row[col]?.[index] || '').padEnd(width)).join(' | ') + ' |'), border]
    })].join('\n')
  }
  for (const table of doc.querySelectorAll('.markdown-table-wrap > table')) {
    if (!table.parentElement.closest('td')) table.parentElement.replaceWith(doc.createTextNode(tableText(table) + '\n'))
  }
  for (const item of doc.querySelectorAll('li')) {
    const marker = item.parentElement.tagName === 'OL' ? `${Array.from(item.parentElement.children).indexOf(item) + 1}. ` : '- '
    item.prepend(doc.createTextNode(marker))
    item.append('\n')
  }
  for (const br of doc.querySelectorAll('br')) br.replaceWith(doc.createTextNode('\n'))
  for (const field of doc.querySelectorAll('.copy-field-label')) field.append(': ')
  return Array.from(doc.body.childNodes).map(node => node.textContent).join('\n\n')
}
