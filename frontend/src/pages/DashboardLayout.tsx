import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import clsx from 'clsx'
import { useStore } from '../store/useStore'

export default function DashboardLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const currentProfile = useStore((s) => s.currentProfile)
  
  // Get time-based greeting
  const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 17) return 'Good afternoon'
    return 'Good evening'
  }
  
  // Determine active tab from URL
  const getActiveTab = () => {
    if (location.pathname.includes('/dashboard/generate')) return 'generate'
    if (location.pathname.includes('/dashboard/schedules')) return 'schedules'
    return 'briefs'
  }
  
  const activeTab = getActiveTab()

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
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
            onClick={() => navigate('/dashboard/generate')}
            className={clsx(
              'px-4 sm:px-6 py-2 sm:py-2.5 rounded-full text-sm sm:text-base font-medium transition-all',
              activeTab === 'generate'
                ? 'bg-accent text-white'
                : 'text-augustus-300 hover:text-white'
            )}
          >
            Generate
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
    </div>
  )
}

