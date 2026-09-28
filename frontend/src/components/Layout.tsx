import { useMemo } from 'react'
import { Outlet, NavLink, Link, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Tag,
  Settings,
  Users,
  ChevronRight,
  Plug
} from 'lucide-react'
import clsx from 'clsx'
import { version } from '../../package.json'
import AudioPlayer from './AudioPlayer'
import { useStore } from '../store/useStore'
import { useProfileSlug } from '../utils/profileSlug'

// Get initials from a name (max 2 characters)
function getInitials(name: string): string {
  const words = name.trim().split(/\s+/)
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
}

const baseNavItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', adminOnly: false },
  { path: '/topics', icon: Tag, label: 'Topics', adminOnly: false },
  { path: '/casts', icon: Users, label: 'Casts', adminOnly: false },
  { path: '/mcp', icon: Plug, label: 'MCP', adminOnly: true },
  { path: '/settings', icon: Settings, label: 'Settings', adminOnly: true },
]

// Mobile bottom nav shows only the most important items
const baseMobileNavItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Home', adminOnly: false },
  { path: '/topics', icon: Tag, label: 'Topics', adminOnly: false },
  { path: '/casts', icon: Users, label: 'Casts', adminOnly: false },
  { path: '/settings', icon: Settings, label: 'Settings', adminOnly: true },
]

export default function Layout() {
  const currentAudio = useStore((s) => s.currentAudio)
  const currentProfile = useStore((s) => s.currentProfile)
  const navigate = useNavigate()
  const profileSlug = useProfileSlug()
  const profileInitials = currentProfile?.name ? getInitials(currentProfile.name) : '?'
  const profileColor = currentProfile?.color || '#e85d04'
  
  // Filter nav items based on admin status and prefix with profile slug
  const isAdmin = currentProfile?.is_admin ?? false
  const navItems = useMemo(() =>
    baseNavItems
      .filter(item => !item.adminOnly || isAdmin)
      .map(item => ({ ...item, to: `/${profileSlug}${item.path}` })),
    [isAdmin, profileSlug]
  )
  const mobileNavItems = useMemo(() =>
    baseMobileNavItems
      .filter(item => !item.adminOnly || isAdmin)
      .map(item => ({ ...item, to: `/${profileSlug}${item.path}` })),
    [isAdmin, profileSlug]
  )
  
  return (
    <div className="h-[100dvh] flex flex-col md:flex-row overflow-hidden">
      {/* Mobile Header */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 bg-augustus-900/80 backdrop-blur-xl border-b border-augustus-800/50 flex-shrink-0 pt-safe">
        <Link to={`/${profileSlug}/dashboard`} className="flex items-center cursor-pointer hover:opacity-80 transition-opacity pt-2">
          <img src="/augustus-logo.png" alt="Augustus" className="h-[1.15rem]" />
        </Link>
        <button
          onClick={() => navigate('/profiles')}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold text-white shadow-md hover:opacity-80 active:scale-95 transition-all"
          style={{ backgroundColor: profileColor }}
          aria-label={currentProfile?.name ? `Switch profile (${currentProfile.name})` : 'Select profile'}
          title={currentProfile?.name ? `${currentProfile.name} — switch profile` : 'Select profile'}
        >
          {profileInitials}
        </button>
      </header>
      
      {/* Sidebar - desktop only */}
      <aside className="hidden md:flex md:w-64 bg-augustus-900/95 backdrop-blur-xl border-r border-augustus-800/50 flex-col flex-shrink-0 relative z-50">
        {/* Logo */}
        <div className="px-6 pb-6 pt-6 border-b border-augustus-800/50 flex items-center justify-between" style={{ paddingTop: 'calc(1.5rem + env(safe-area-inset-top, 0px))' }}>
          <Link to={`/${profileSlug}/dashboard`} className="flex items-center cursor-pointer hover:opacity-80 transition-opacity flex-1 pt-4">
            <img src="/augustus-logo.png" alt="Augustus" className="h-[1.44rem]" />
          </Link>
        </div>
        
        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-auto">
          <ul className="space-y-2">
            {navItems.map(({ to, icon: Icon, label }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 touch-target',
                      isActive
                        ? 'bg-accent/10 text-accent border border-accent/20'
                        : 'text-augustus-400 hover:text-augustus-100 hover:bg-augustus-800/50 active:bg-augustus-800'
                    )
                  }
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        
        {/* Footer with Profile Switcher */}
        <div className="p-4 border-t border-augustus-800/50 flex-shrink-0 pb-safe">
          {/* Profile Button */}
          <button
            onClick={() => navigate('/profiles')}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-augustus-800/50 hover:bg-augustus-800 transition-colors group mb-3"
          >
            <div 
              className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold text-white shadow-md"
              style={{ backgroundColor: profileColor }}
            >
              {profileInitials}
            </div>
            <div className="flex-1 text-left min-w-0">
              <p className="text-sm font-medium text-augustus-100 truncate">
                {currentProfile?.name || 'Select Profile'}
              </p>
              <p className="text-xs text-augustus-500">Switch profile</p>
            </div>
            <ChevronRight className="w-4 h-4 text-augustus-500 group-hover:text-augustus-300 transition-colors" />
          </button>
          
          <p className="text-xs text-augustus-600 text-center">
            Augustus v{version}
          </p>
        </div>
      </aside>
      
      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Scrollable page content */}
        <main className="flex-1 overflow-auto scroll-smooth">
          <Outlet />
        </main>
        
        {/* Audio player - above bottom nav on mobile */}
        {currentAudio && (
          <div className="flex-shrink-0 border-t border-augustus-800/50 bg-augustus-900/95 backdrop-blur-xl shadow-2xl shadow-black/50">
            <AudioPlayer />
          </div>
        )}
        
        {/* Mobile Bottom Navigation */}
        <nav className="md:hidden flex-shrink-0 bg-augustus-900/95 backdrop-blur-xl border-t border-augustus-800/50 bottom-nav">
          <div className="flex items-center justify-around">
            {mobileNavItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  clsx(
                    'flex flex-col items-center justify-center py-2 px-3 min-w-[64px] transition-colors',
                    isActive
                      ? 'text-accent'
                      : 'text-augustus-500 active:text-augustus-300'
                  )
                }
              >
                <Icon className="w-6 h-6 mb-1" />
                <span className="text-[10px] font-medium">{label}</span>
              </NavLink>
            ))}
          </div>
        </nav>
      </div>
    </div>
  )
}
