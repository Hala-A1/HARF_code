import { Columns2, Globe2, PanelTop } from 'lucide-react'
import { useState } from 'react'

export default function BilingualView({ languages, renderLanguage }) {
  // Keep English left and Arabic right, regardless of API object key order.
  const orderedLanguages = [...new Set(languages)].sort((a, b) => {
    const rank = { en: 0, ar: 1 }
    return (rank[a] ?? 2) - (rank[b] ?? 2)
  })
  const [layout, setLayout] = useState('split')
  const [active, setActive] = useState('en')
  const selected = orderedLanguages.includes(active) ? active : orderedLanguages[0]
  const dual = languages.length > 1
  return <div dir="ltr" className={`bilingual-view ${dual && layout === 'split' ? 'bilingual-split' : 'bilingual-tabs'}`}>
    {dual && <div className="bilingual-toolbar"><span><Globe2 size={15} /> Two languages. One clear view.</span><div className="bilingual-layout" role="group" aria-label="Output layout">
      <button type="button" aria-pressed={layout === 'split'} onClick={() => setLayout('split')}><Columns2 size={15} /> Side by side</button>
      <button type="button" aria-pressed={layout === 'tabs'} onClick={() => setLayout('tabs')}><PanelTop size={15} /> One language</button>
    </div></div>}
    {dual && layout === 'tabs' && <div className="bilingual-language-tabs" role="group" aria-label="Visible output language">{orderedLanguages.map(language => <button type="button" key={language} aria-pressed={selected === language} onClick={() => setActive(language)}>{language === 'ar' ? 'العربية' : 'English'}</button>)}</div>}
    <div className="bilingual-columns">{orderedLanguages.map(language => <div className="bilingual-column" key={language} hidden={dual && layout === 'tabs' && language !== selected} lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'}><div className="bilingual-column-heading"><span>{language === 'ar' ? 'العربية' : 'English'}</span><small>{language === 'ar' ? 'AR' : 'EN'}</small></div>{renderLanguage(language)}</div>)}</div>
  </div>
}
