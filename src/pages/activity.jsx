import { useNavigate } from 'react-router-dom'
import HarfLogo from '../components/HarfLogo'
import ActivityTracker from '../components/activity-tracker'
import RequestLimits from '../components/request-limits'
import { getActiveChannel } from '../auth'

export default function ActivityPage() {
  const navigate = useNavigate()
  return <main className="personal-activity"><header><HarfLogo compact /><button type="button" onClick={() => navigate('/choose')}>Back to workspace</button></header><RequestLimits key={getActiveChannel()} channelId={getActiveChannel()} personal /><ActivityTracker initialChannel={getActiveChannel()} /></main>
}
