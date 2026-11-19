import test from 'node:test'
import assert from 'node:assert/strict'
import { markdownToHtml } from '../../src/markdown.js'

test('emphasis renders without changing literal code or admitting HTML', () => {
  const html = markdownToHtml('A **bold** and *italic* word, _another_ word and `**literal**`.\n<script>unsafe</script>')
  assert.ok(html.includes('<strong>bold</strong>'))
  assert.ok(html.includes('<em>italic</em>'))
  assert.ok(html.includes('<em>another</em>'))
  assert.ok(html.includes('<code>**literal**</code>'))
  assert.ok(html.includes('&lt;script&gt;'))
})

test('preserved Markdown source stays inside its outer fence', () => {
  const html = markdownToHtml('## Source reference\n````text\n# Original heading\n```yaml\nrequired: true\n```\n<script>alert(1)</script>\n````\n## Active template')
  assert.equal((html.match(/<pre>/g) || []).length, 1)
  assert.ok(html.includes('# Original heading\n```yaml\nrequired: true\n```'))
  assert.ok(html.includes('&lt;script&gt;'))
  assert.ok(html.endsWith('<h2>Active template</h2>'))
})

test('component index links and tables stay navigable', () => {
  const html = markdownToHtml('| ID | Definition |\n|---|---|\n| B2B-COMPONENT-004 | [Component 4](#b2b-component-004) |\n\n<a id="b2b-component-004"></a>\n### Component 4 — USP Featured')
  assert.ok(html.includes('<table>'))
  assert.ok(html.includes('href="#b2b-component-004"'))
  assert.ok(html.includes('id="b2b-component-004"'))
})
