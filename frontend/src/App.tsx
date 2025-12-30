import { useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { settingsApi } from './api/client'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import BriefingDetail from './pages/BriefingDetail'
import Topics from './pages/Topics'
import CreateTopic from './pages/CreateTopic'
import Casts from './pages/Casts'
import CreateCast from './pages/CreateCast'
import ManagePersonalities from './pages/ManagePersonalities'
import Settings from './pages/Settings'
import About from './pages/About'
import Onboarding from './pages/Onboarding'

// Component that checks if user needs onboarding
function OnboardingCheck({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()

  // Fetch settings to check onboarding state
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })

  useEffect(() => {
    if (settings) {
      const hasOnboarded = settings.onboarding_completed
      const wasSkipped = settings.onboarding_skipped
      // Redirect to onboarding if not completed, not skipped, and not already on onboarding page
      if (!hasOnboarded && !wasSkipped && location.pathname !== '/onboarding') {
        navigate('/onboarding', { replace: true })
      }
    }
  }, [navigate, location.pathname, settings])

  return <>{children}</>
}

function App() {
  return (
    <OnboardingCheck>
      <Routes>
        {/* Onboarding route - outside main layout */}
        <Route path="/onboarding" element={<Onboarding />} />
        
        {/* Main app with layout */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="briefing/:id" element={<BriefingDetail />} />
          <Route path="topics" element={<Topics />} />
          <Route path="topics/create" element={<CreateTopic />} />
          <Route path="casts" element={<Casts />} />
          <Route path="casts/create" element={<CreateCast />} />
          <Route path="casts/personalities" element={<ManagePersonalities />} />
          <Route path="settings" element={<Settings />} />
          <Route path="about" element={<About />} />
        </Route>
      </Routes>
    </OnboardingCheck>
  )
}

export default App

