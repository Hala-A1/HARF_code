import './harf-brand.css'
import HarfIcon from './HarfIcon.jsx'

export default function BrandLogo({ style, compact = false, className = '' }) {
  return <span className={`brand-wordmark harf-wordmark ${compact ? 'harf-wordmark--compact' : 'harf-wordmark--bilingual'} ${className}`.trim()} style={style} dir="ltr" role="img" aria-label="Harf حرف">
    <HarfIcon className="harf-wordmark__symbol" label="" />
    <span className="harf-wordmark__latin" lang="en" aria-hidden="true">Harf</span>
  </span>
}
