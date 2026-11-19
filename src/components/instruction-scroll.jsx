import { ArrowUpToLine, ArrowDownToLine } from 'lucide-react'
import './instruction-scroll.css'

export default function InstructionScroll({ editorSelector }) {
  function jump(bottom) {
    const editor = document.querySelector(editorSelector)
    if (editor) {
      editor.scrollTo({ top: bottom ? editor.scrollHeight : 0, behavior: 'instant' })
      editor.scrollIntoView({ block: 'center', behavior: 'instant' })
    } else {
      window.scrollTo({ top: bottom ? document.documentElement.scrollHeight : 0, behavior: 'instant' })
    }
  }

  return <nav className="instruction-scroll" aria-label="Jump through instructions">
    <button type="button" onClick={() => jump(false)} title="Jump to the top of instructions"><ArrowUpToLine size={17} /> Top</button>
    <button type="button" onClick={() => jump(true)} title="Jump to the bottom of instructions"><ArrowDownToLine size={17} /> Bottom</button>
  </nav>
}
