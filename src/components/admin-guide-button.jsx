import { FileText } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getActiveChannel, getProfile, isSignedIn } from '../auth'
import './admin-guide-button.css'

export default function AdminGuideButton({ className = '' }) {
  const navigate = useNavigate()
  if (!isSignedIn() || getProfile()?.role === 'approval_admin') return null

  return (
    <button
      className={`admin-guide-btn ${className}`.trim()}
      type="button"
      onClick={() => navigate(`/guidelines?channel=${getActiveChannel() || 'b2b'}`)}
      aria-label="View and edit Harf writing guidelines"
      title="View and edit Harf guidelines"
    >
      <FileText size={18} aria-hidden="true" />
      <span className="sr-only">CX guidelines</span>
    </button>
  )
}
