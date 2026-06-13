import { useEffect } from 'react'
import { X } from 'lucide-react'
import DashboardGenerate from '../pages/DashboardGenerate'

interface GenerateSheetProps {
  open: boolean
  onClose: () => void
}

/**
 * Generate form presented as a bottom sheet on mobile and a centered
 * dialog on desktop, so users can create a briefing from anywhere on
 * the dashboard without switching tabs.
 */
export default function GenerateSheet({ open, onClose }: GenerateSheetProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-label="Generate new briefing">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />

      {/* Panel: bottom sheet on mobile, centered dialog on sm+ */}
      <div className="absolute inset-x-0 bottom-0 sm:inset-0 sm:flex sm:items-center sm:justify-center pointer-events-none">
        <div className="pointer-events-auto bg-augustus-900 border-t sm:border border-augustus-700/60 rounded-t-3xl sm:rounded-2xl shadow-2xl shadow-black/60 w-full sm:max-w-2xl max-h-[88dvh] sm:max-h-[85dvh] overflow-y-auto overscroll-contain pb-safe animate-sheet-up">
          {/* Grab handle (mobile) + close */}
          <div className="sticky top-0 z-10 bg-augustus-900/95 backdrop-blur-sm rounded-t-3xl sm:rounded-t-2xl">
            <div className="sm:hidden flex justify-center pt-3">
              <div className="w-10 h-1 rounded-full bg-augustus-700" />
            </div>
            <div className="flex justify-end px-3 pt-2">
              <button
                onClick={onClose}
                className="btn btn-ghost p-2 min-h-[44px] min-w-[44px] text-augustus-400 hover:text-white"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
          <div className="px-4 sm:px-6 pb-6 -mt-2">
            <DashboardGenerate />
          </div>
        </div>
      </div>
    </div>
  )
}
