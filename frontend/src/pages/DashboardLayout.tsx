import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Plus } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store/useStore'
import { useProfileNavigate } from '../utils/profileSlug'
import GenerateSheet from '../components/GenerateSheet'

export default function DashboardLayout() {
  const navigate = useProfileNavigate()
  const location = useLocation()
  const currentProfile = useStore((s) => s.currentProfile)
  const currentAudio = useStore((s) => s.currentAudio)
  const [generateOpen, setGenerateOpen] = useState(false)

  // Get time-based greeting
  const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 17) return 'Good afternoon'
    return 'Good evening'
  }

  // Determine active tab from URL
  const getActiveTab = () => {
    if (location.pathname.includes('/dashboard/schedules')) return 'schedules'
    return 'briefs'
  }

  const activeTab = getActiveTab()

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
            {currentProfile ? (
              <>
                {getGreeting()}, {currentProfile.name}
              </>
            ) : (
              'Dashboard'
            )}
          </h1>
          <p className="text-sm sm:text-base text-augustus-400">
            AI-generated audio briefings from your news feeds
          </p>
        </div>
        {/* Desktop: header action. Mobile uses the floating button below. */}
        <button
          onClick={() => setGenerateOpen(true)}
          className="hidden sm:flex btn btn-primary items-center gap-2 flex-shrink-0"
        >
          <Plus className="w-5 h-5" />
          New briefing
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="mb-6 sm:mb-8">
        <div className="inline-flex bg-augustus-800/50 p-1 rounded-full">
          <button
            onClick={() => navigate('/dashboard/briefs')}
            className={clsx(
              'px-4 sm:px-6 py-2 sm:py-2.5 rounded-full text-sm sm:text-base font-medium transition-all',
              activeTab === 'briefs'
                ? 'bg-accent text-white'
                : 'text-augustus-300 hover:text-white'
            )}
          >
            Briefs
          </button>
          <button
            onClick={() => navigate('/dashboard/schedules')}
            className={clsx(
              'px-4 sm:px-6 py-2 sm:py-2.5 rounded-full text-sm sm:text-base font-medium transition-all',
              activeTab === 'schedules'
                ? 'bg-accent text-white'
                : 'text-augustus-300 hover:text-white'
            )}
          >
            Schedules
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <Outlet />

      {/* Mobile floating action button */}
      <button
        onClick={() => setGenerateOpen(true)}
        className={clsx(
          'sm:hidden fixed right-4 z-40 w-14 h-14 rounded-full bg-accent hover:bg-accent-600 text-white shadow-2xl shadow-accent/30 flex items-center justify-center active:scale-95 transition-all',
          currentAudio ? 'bottom-48' : 'bottom-24'
        )}
        aria-label="New briefing"
      >
        <Plus className="w-7 h-7" />
      </button>

      <GenerateSheet open={generateOpen} onClose={() => setGenerateOpen(false)} />
    </div>
  )
}
