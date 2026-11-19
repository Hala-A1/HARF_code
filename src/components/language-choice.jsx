export default function LanguageChoice({ value, onChange, disabled = false, originalMode = false }) {
  const selected = originalMode ? '' : value.includes('en') && value.includes('ar') ? 'both' : value[0]
  return <fieldset className="copywriter-languages language-choice">
    <legend>Show generated text in</legend>
    <div className="language-choice-options" role="group" aria-label="Output language">
      {[['en', 'English'], ['ar', 'Arabic'], ['both', 'Both']].map(([key, label]) => <button key={key} type="button" aria-pressed={selected === key} disabled={disabled} onClick={() => onChange(key === 'both' ? ['en', 'ar'] : [key])}>{label}</button>)}
    </div>
    <small>{originalMode ? 'Using each spreadsheet row’s original language. Choose an option above to replace it.' : selected === 'both' ? 'Generate and show English and Arabic together.' : 'Choose English, Arabic or both for your output.'}</small>
  </fieldset>
}
