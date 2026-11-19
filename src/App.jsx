import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import SignIn from './pages/signin.jsx'
import ChooseWorkspace from './pages/choose-workspace.jsx'
import Copywriter from './pages/copywriter.jsx'
import Admin from './pages/admin.jsx'
import OnboardingTutorial from './components/onboarding-tutorial.jsx'
import RequestLimitNotice from './components/request-limit-notice.jsx'
import { canAccessWorkspace, isSignedIn } from './auth.js'
import './theme.css'

const ActivityPage = lazy(() => import('./pages/activity.jsx'))
const Guidelines = lazy(() => import('./pages/guidelines.jsx'))

function SignedIn({ children }) {
  return isSignedIn() ? children : <Navigate to="/" replace />
}

function WorkspaceAccess({ workspace, children }) {
  return canAccessWorkspace(workspace) ? children : <Navigate to="/choose" replace />
}

function App() {
  return (
    <BrowserRouter>
      <RequestLimitNotice />
      <OnboardingTutorial />
      <Routes>
        <Route path="/" element={<SignIn />} />
        <Route path="/choose" element={<SignedIn><ChooseWorkspace /></SignedIn>} />
        <Route path="/guidelines" element={<SignedIn><Suspense fallback={<p>Loading guidelines...</p>}><Guidelines /></Suspense></SignedIn>} />
        <Route path="/copywriter" element={<SignedIn><WorkspaceAccess workspace="rewrite"><Copywriter /></WorkspaceAccess></SignedIn>} />
        <Route path="/activity" element={<SignedIn><WorkspaceAccess workspace="rewrite"><Suspense fallback={<p>Loading activity…</p>}><ActivityPage /></Suspense></WorkspaceAccess></SignedIn>} />
        <Route path="/admin" element={<SignedIn><Admin /></SignedIn>} />
        <Route path="/admin/:channelId" element={<SignedIn><Admin /></SignedIn>} />
        <Route path="*" element={<Navigate to="/choose" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
