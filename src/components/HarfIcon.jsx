import './harf-brand.css'
const logo = '/harf-logo.svg'

export default function HarfIcon({ className = '', label = 'Harf logo' }) {
  return <img className={`harf-writing-icon harf-symbol ${className}`.trim()} src={logo} alt={label} aria-hidden={!label || undefined} draggable="false" />
}
