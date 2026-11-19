function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function inline(value) {
  return value.split(/(`[^`]+`|\*\*.+?\*\*|(?<!\*)\*[^*\n]+\*(?!\*)|(?<!\w)_[^_\n]+_(?!\w))/g).map(part => {
    if (/^`[^`]+`$/.test(part)) return `<code>${escapeHtml(part.slice(1, -1))}</code>`
    if (/^\*\*.+\*\*$/.test(part)) return `<strong>${inline(part.slice(2, -2))}</strong>`
    if (/^\*[^*]+\*$/.test(part) || /^_[^_]+_$/.test(part)) return `<em>${inline(part.slice(1, -1))}</em>`
    return escapeHtml(part)
      .replace(/&lt;br\s*\/?&gt;/gi, '<br />')
      .replace(/\[([^\]\n]+)\]\((#[a-zA-Z0-9_-]+|[a-zA-Z0-9_-]+\.md)\)/g, '<a href="$2">$1</a>')
  }).join('')
}

export function markdownToHtml(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n')
  const html = []
  let inList = null
  let inCode = false
  let fenceCharacter = ''
  let fenceLength = 0
  let codeLines = []

  function closeList() {
    if (inList) {
      html.push(`</${inList}>`)
      inList = null
    }
  }

  function cells(line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'))
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const fence = line.trim().match(/^(`{3,}|~{3,})(.*)$/)
    if (fence && (!inCode || (fence[1][0] === fenceCharacter && fence[1].length >= fenceLength && !fence[2].trim()))) {
      closeList()
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
        codeLines = []
        inCode = false
      } else {
        inCode = true
        fenceCharacter = fence[1][0]
        fenceLength = fence[1].length
      }
      continue
    }

    if (inCode) {
      codeLines.push(line)
      continue
    }

    const anchor = line.trim().match(/^<a id="([a-zA-Z0-9_-]+)"><\/a>$/)
    if (anchor) {
      closeList()
      html.push(`<a id="${anchor[1]}"></a>`)
      continue
    }
    if (/^\s*<!--.*-->\s*$/.test(line)) continue

    const separator = index + 1 < lines.length ? cells(lines[index + 1]) : []
    const headers = cells(line)
    if (line.includes('|') && separator.length === headers.length && separator.every((cell) => /^:?-{3,}:?$/.test(cell))) {
      closeList()
      html.push('<div class="markdown-table-wrap"><table><thead><tr>')
      headers.forEach((cell) => html.push(`<th scope="col">${inline(cell)}</th>`))
      html.push('</tr></thead><tbody>')
      index += 2
      while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
        const row = cells(lines[index])
        html.push('<tr>')
        headers.forEach((_, column) => html.push(`<td>${inline(row[column] || '')}</td>`))
        html.push('</tr>')
        index += 1
      }
      index -= 1
      html.push('</tbody></table></div>')
      continue
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/)
    const unordered = line.match(/^[-*]\s+(.+)$/)
    const ordered = line.match(/^\d+\.\s+(.+)$/)
    const quote = line.match(/^>\s?(.*)$/)

    if (heading) {
      closeList()
      const level = heading[1].length
      html.push(`<h${level}>${inline(heading[2])}</h${level}>`)
      continue
    }

    if (line.trim() === '---') {
      closeList()
      html.push('<hr />')
      continue
    }

    if (quote) {
      closeList()
      html.push(`<blockquote>${inline(quote[1])}</blockquote>`)
      continue
    }

    if (unordered) {
      if (inList !== 'ul') {
        closeList()
        html.push('<ul>')
        inList = 'ul'
      }
      html.push(`<li>${inline(unordered[1])}</li>`)
      continue
    }

    if (ordered) {
      if (inList !== 'ol') {
        closeList()
        html.push('<ol>')
        inList = 'ol'
      }
      html.push(`<li>${inline(ordered[1])}</li>`)
      continue
    }

    closeList()
    if (!line.trim()) continue
    html.push(`<p>${inline(line)}</p>`)
  }

  closeList()
  if (inCode) html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
  return html.join('')
}
