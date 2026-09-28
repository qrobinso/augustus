import { useState, type ReactNode } from 'react'
import { Key, Eye, EyeOff, ExternalLink, type LucideIcon } from 'lucide-react'
import { SETTINGS_GROUPS } from './settingsLogic'

/** Password-style API key field with a key icon and a show/hide toggle. */
export function SecretInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
}) {
  const [shown, setShown] = useState(false)
  return (
    <div className="relative">
      <Key className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 sm:w-5 h-4 sm:h-5 text-augustus-500" />
      <input
        type={shown ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="input pl-10 sm:pl-12 pr-10 sm:pr-12"
      />
      <button
        type="button"
        onClick={() => setShown(!shown)}
        aria-label={shown ? 'Hide key' : 'Show key'}
        className="absolute right-3 sm:right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300 p-1"
      >
        {shown ? <EyeOff className="w-4 sm:w-5 h-4 sm:h-5" /> : <Eye className="w-4 sm:w-5 h-4 sm:h-5" />}
      </button>
    </div>
  )
}

/** Styled checkbox row with a title and helper text. */
export function SettingsCheckbox({
  checked,
  onChange,
  title,
  description,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  title: string
  description: string
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <div className="relative flex items-center justify-center mt-0.5">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />
        <div className="w-5 h-5 border-2 border-augustus-600 rounded bg-augustus-800 peer-checked:bg-accent peer-checked:border-accent transition-colors flex items-center justify-center">
          {checked && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
      </div>
      <div className="flex-1">
        <span className="text-sm font-medium text-white group-hover:text-accent transition-colors">
          {title}
        </span>
        <p className="text-xs text-augustus-400 mt-1">
          {description}
        </p>
      </div>
    </label>
  )
}

/** Full-width card button that leads to another page. */
export function SettingsLinkCard({
  icon: Icon,
  title,
  description,
  onClick,
}: {
  icon: LucideIcon
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="w-full card hover:border-augustus-600 transition-colors cursor-pointer group active:scale-[0.99] flex items-center justify-between"
    >
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5 text-accent flex-shrink-0" />
        <div className="text-left">
          <h3 className="text-base sm:text-lg font-semibold text-white group-hover:text-accent transition-colors">
            {title}
          </h3>
          <p className="text-xs sm:text-sm text-augustus-400 mt-0.5">
            {description}
          </p>
        </div>
      </div>
      <ExternalLink className="w-5 h-5 text-augustus-600 group-hover:text-augustus-400 transition-colors flex-shrink-0" />
    </button>
  )
}

/**
 * A headed group of settings cards. The scroll margin keeps the heading clear of the
 * sticky jump bar when a jump link scrolls it into view.
 */
export function SettingsGroup({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description?: string
  children: ReactNode
}) {
  const headingId = `${id}-heading`
  return (
    <section id={id} aria-labelledby={headingId} className="scroll-mt-20 mb-8 sm:mb-10">
      <div className="mb-3 sm:mb-4 border-b border-augustus-800 pb-2">
        <h2 id={headingId} className="text-xs sm:text-sm font-semibold uppercase tracking-wider text-augustus-300">
          {title}
        </h2>
        {description && (
          <p className="mt-0.5 text-xs text-augustus-500">{description}</p>
        )}
      </div>
      {children}
    </section>
  )
}

/**
 * Compact jump links, sticky to the top of the app's scroll container (<main>).
 * Negative margins cancel the page-container gutter so the bar spans the full width
 * without causing horizontal scroll.
 */
export function SettingsJumpBar() {
  const jumpTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <nav
      aria-label="Settings sections"
      className="sticky top-0 z-20 -mx-4 sm:-mx-6 lg:-mx-8 mb-4 sm:mb-6 border-b border-augustus-800/50 bg-augustus-950/90 px-4 sm:px-6 lg:px-8 py-2 backdrop-blur-xl"
    >
      <ul className="flex items-center gap-1">
        {SETTINGS_GROUPS.map(({ id, label }, index) => (
          <li key={id} className="flex items-center gap-1">
            {index > 0 && <span aria-hidden="true" className="text-augustus-600">·</span>}
            <button
              type="button"
              onClick={() => jumpTo(id)}
              className="whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium text-augustus-300 transition-colors hover:bg-augustus-800 hover:text-white active:bg-augustus-700"
            >
              {label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
