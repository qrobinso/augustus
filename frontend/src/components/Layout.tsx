import { useState, useEffect } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Globe,
  Tag,
  Settings,
  Waves,
  Menu,
  X,
  Users
} from 'lucide-react'
import clsx from 'clsx'
import AudioPlayer from './AudioPlayer'
import { useStore } from '../store/useStore'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/topics', icon: Tag, label: 'Topics' },
  { to: '/custom-sites', icon: Globe, label: 'Sites' },
  { to: '/casts', icon: Users, label: 'Casts' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

// Mobile bottom nav shows only the most important items
const mobileNavItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Home' },
  { to: '/topics', icon: Tag, label: 'Topics' },
  { to: '/custom-sites', icon: Globe, label: 'Sites' },
  { to: '/casts', icon: Users, label: 'Casts' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const currentAudio = useStore((s) => s.currentAudio)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  
  // Close sidebar when route changes
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])
  
  // Prevent body scroll when sidebar is open
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [sidebarOpen])
  
  return (
    <div className="h-[100dvh] flex flex-col md:flex-row overflow-hidden">
      {/* Mobile Header */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 bg-augustus-900/80 backdrop-blur-xl border-b border-augustus-800/50 flex-shrink-0 pt-safe">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-accent-700 flex items-center justify-center">
            <Waves className="w-5 h-5 text-white" />
          </div>
          <h1 className="font-display text-lg font-semibold text-white">Augustus</h1>
        </div>
        <button
          onClick={() => setSidebarOpen(true)}
          className="btn-icon btn btn-ghost"
          aria-label="Open menu"
        >
          <Menu className="w-6 h-6" />
        </button>
      </header>
      
      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="md:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Sidebar - Desktop: always visible, Mobile: slide-in drawer */}
      <aside 
        className={clsx(
          'bg-augustus-900/95 backdrop-blur-xl border-r border-augustus-800/50 flex flex-col flex-shrink-0 z-50',
          // Desktop styles
          'md:w-64 md:relative md:translate-x-0',
          // Mobile styles - slide-in from left
          'fixed inset-y-0 left-0 w-72 transform transition-transform duration-300 ease-out',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="p-6 border-b border-augustus-800/50 flex items-center justify-between pt-safe">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-accent-700 flex items-center justify-center">
              <Waves className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-display text-xl font-semibold text-white">Augustus</h1>
              <p className="text-xs text-augustus-500">Audio Intelligence</p>
            </div>
          </div>
          {/* Close button - mobile only */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden btn-icon btn btn-ghost"
            aria-label="Close menu"
          >
            <X className="w-6 h-6" />
          </button>
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
        
        {/* Footer */}
        <div className="p-4 border-t border-augustus-800/50 flex-shrink-0 pb-safe">
          <p className="text-xs text-augustus-600 text-center">
            OpenHuxe v0.1.0
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
