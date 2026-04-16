import { useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { settingsApi, profilesApi } from './api/client'
import { useStore } from './store/useStore'
import { slugify } from './utils/profileSlug'
import Layout from './components/Layout'
import DashboardLayout from './pages/DashboardLayout'
import DashboardBriefs from './pages/DashboardBriefs'
import DashboardGenerate from './pages/DashboardGenerate'
import DashboardSchedules from './pages/DashboardSchedules'
import BriefingDetail from './pages/BriefingDetail'
import Topics from './pages/Topics'
import CreateTopic from './pages/CreateTopic'
import EditSite from './pages/EditSite'
import Casts from './pages/Casts'
import CreateCast from './pages/CreateCast'
import CreateSchedule from './pages/CreateSchedule'
import ManagePersonalities from './pages/ManagePersonalities'
import Settings from './pages/Settings'
import About from './pages/About'
import Onboarding from './pages/Onboarding'
import ProfileSwitcher from './pages/ProfileSwitcher'

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

// Component that checks if user has selected a profile
function ProfileCheck({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { currentProfile, setCurrentProfile, setProfiles } = useStore()

  // Fetch profiles to populate store
  const { data: profilesData, isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: () => profilesApi.list(),
  })

  useEffect(() => {
    if (profilesData) {
      setProfiles(profilesData.profiles)

      // If no current profile is selected but we have profiles, auto-select
      if (!currentProfile && profilesData.profiles.length > 0) {
        // Check if we have a stored profile ID that still exists
        const storedProfileId = localStorage.getItem('currentProfileId')
        const storedProfile = storedProfileId ? profilesData.profiles.find(p => p.id === storedProfileId) : null
        if (storedProfile) {
          setCurrentProfile(storedProfile)
        } else {
          // Auto-select the default profile or first profile
          const defaultProfile = profilesData.profiles.find(p => p.is_admin) || profilesData.profiles[0]
          setCurrentProfile(defaultProfile)
        }
      }
    }
  }, [profilesData, currentProfile, setCurrentProfile, setProfiles])

  // Skip profile check for certain routes
  const skipProfileCheck = ['/profiles', '/onboarding', '/settings'].some(
    path => location.pathname.startsWith(path)
  )

  // Wait for loading
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  // Redirect to profile selector if no profile and not on exempt route
  if (!skipProfileCheck && !currentProfile && profilesData?.profiles && profilesData.profiles.length > 1) {
    return <Navigate to="/profiles" replace />
  }

  return <>{children}</>
}

// Component that syncs profile slug from URL with the profile store
function ProfileSlugSync({ children }: { children: React.ReactNode }) {
  const { profileSlug } = useParams<{ profileSlug: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { currentProfile, profiles, setCurrentProfile } = useStore()

  useEffect(() => {
    if (!profileSlug || profiles.length === 0) return

    // Find profile matching the URL slug
    const matchedProfile = profiles.find(p => slugify(p.name) === profileSlug)

    if (matchedProfile) {
      // If URL slug matches a different profile, switch to it
      if (!currentProfile || currentProfile.id !== matchedProfile.id) {
        setCurrentProfile(matchedProfile)
      }
    } else if (currentProfile) {
      // URL slug doesn't match any profile - redirect to current profile's slug
      const correctSlug = slugify(currentProfile.name)
      const restOfPath = location.pathname.replace(`/${profileSlug}`, '')
      navigate(`/${correctSlug}${restOfPath}`, { replace: true })
    }
  }, [profileSlug, profiles, currentProfile, setCurrentProfile, navigate, location.pathname])

  return <>{children}</>
}

// Redirect from root to the current profile's dashboard
function RootRedirect() {
  const { currentProfile } = useStore()
  if (currentProfile) {
    return <Navigate to={`/${slugify(currentProfile.name)}/dashboard`} replace />
  }
  return <Navigate to="/profiles" replace />
}

function App() {
  return (
    <OnboardingCheck>
      <ProfileCheck>
        <Routes>
          {/* Onboarding route - outside main layout */}
          <Route path="/onboarding" element={<Onboarding />} />

          {/* Profile switcher - outside main layout */}
          <Route path="/profiles" element={<ProfileSwitcher />} />

          {/* Root redirect to profile-scoped dashboard */}
          <Route path="/" element={<RootRedirect />} />

          {/* Profile-scoped routes */}
          <Route path="/:profileSlug" element={<ProfileSlugSync><Layout /></ProfileSlugSync>}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardLayout />}>
              <Route index element={<Navigate to="briefs" replace />} />
              <Route path="briefs" element={<DashboardBriefs />} />
              <Route path="generate" element={<DashboardGenerate />} />
              <Route path="schedules" element={<DashboardSchedules />} />
            </Route>
            <Route path="briefing/:id" element={<BriefingDetail />} />
            <Route path="topics" element={<Topics />} />
            <Route path="topics/create" element={<CreateTopic />} />
            <Route path="topics/:id/edit" element={<CreateTopic />} />
            <Route path="sites/:id/edit" element={<EditSite />} />
            <Route path="casts" element={<Casts />} />
            <Route path="casts/create" element={<CreateCast />} />
            <Route path="casts/:id/edit" element={<CreateCast />} />
            <Route path="casts/personalities" element={<ManagePersonalities />} />
            <Route path="schedules/create" element={<CreateSchedule />} />
            <Route path="schedules/:id/edit" element={<CreateSchedule />} />
            <Route path="settings" element={<Settings />} />
            <Route path="about" element={<About />} />
          </Route>
        </Routes>
      </ProfileCheck>
    </OnboardingCheck>
  )
}

export default App
