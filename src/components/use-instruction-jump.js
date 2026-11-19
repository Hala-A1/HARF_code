import { useRef } from 'react'

export default function useInstructionJump(content, openEditor, onError) {
  const editorRef = useRef(null)
  async function jump(target) {
    const bytes = new TextEncoder().encode(content.replace(/\r\n/g, '\n'))
    const digest = await crypto.subtle.digest('SHA-256', bytes)
    const hash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('').slice(0, 16)
    if (hash !== target.file_version) {
      onError('This recommendation refers to a different saved version. Save or discard your current edits, then refine again to get an accurate location.')
      return
    }
    openEditor()
    window.requestAnimationFrame(() => {
      const editor = editorRef.current
      if (!editor) return
      const offset = content.split('\n').slice(0, target.line - 1).join('\n').length + (target.line > 1 ? 1 : 0)
      editor.focus({ preventScroll: true })
      editor.setSelectionRange(offset, offset)
      const style = getComputedStyle(editor)
      const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.5
      // Include wrapped lines so long paragraphs do not hide the insertion point.
      const mirror = document.createElement('div')
      mirror.style.cssText = `position:absolute;visibility:hidden;white-space:pre-wrap;overflow-wrap:break-word;width:${editor.clientWidth}px;font:${style.font};line-height:${style.lineHeight};padding:${style.padding};box-sizing:border-box;`
      mirror.textContent = content.slice(0, offset) + '\u200b'
      document.body.appendChild(mirror)
      editor.scrollTop = Math.max(0, mirror.offsetHeight - editor.clientHeight / 2 - lineHeight)
      mirror.remove()
      editor.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })
  }
  return { editorRef, jump }
}
