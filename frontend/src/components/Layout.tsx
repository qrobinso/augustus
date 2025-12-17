import { Outlet, NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Mic2, 
  Radio, 
  Settings,
  Waves
} from 'lucide-react'
import clsx from 'clsx'
import AudioPlayer from './AudioPlayer'
import { useStore } from '../store/useStore'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/deepcasts', icon: Mic2, label: 'DeepCasts' },
  { to: '/stations', icon: Radio, label: 'Stations' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const currentAudio = useStore((s) => s.currentAudio)
  
  return (
    <div className="h-screen flex overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-augustus-900/30 border-r border-augustus-800/50 flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="p-6 border-b border-augustus-800/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-accent-700 flex items-center justify-center">
              <Waves className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-display text-xl font-semibold text-white">Augustus</h1>
              <p className="text-xs text-augustus-500">Audio Intelligence</p>
            </div>
          </div>
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
                      'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200',
                      isActive
                        ? 'bg-accent/10 text-accent border border-accent/20'
                        : 'text-augustus-400 hover:text-augustus-100 hover:bg-augustus-800/50'
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
        <div className="p-4 border-t border-augustus-800/50 flex-shrink-0">
          <p className="text-xs text-augustus-600 text-center">
            OpenHuxe v0.1.0
          </p>
        </div>
      </aside>
      
      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Scrollable page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
        
        {/* Audio player - fixed at bottom, never scrolls */}
        {currentAudio && (
          <div className="flex-shrink-0 border-t border-augustus-800/50 bg-augustus-900/95 backdrop-blur-xl shadow-2xl shadow-black/50">
            <AudioPlayer />
          </div>
        )}
      </div>
    </div>
  )
}

