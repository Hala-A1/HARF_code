import { formattedCopyHtml } from '../copy-format.js'
import { useMemo } from 'react'
import './formatted-copy.css'

export default function FormattedCopy({ text = '' }) {
  const html = useMemo(() => formattedCopyHtml(text), [text])
  return <div className="formatted-copy" dangerouslySetInnerHTML={{ __html: html }} />
}
