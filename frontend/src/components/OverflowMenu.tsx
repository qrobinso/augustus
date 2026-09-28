import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Loader2, MoreHorizontal } from 'lucide-react'
import clsx from 'clsx'
import { nextMenuIndex, type MenuKey } from './menuNavigation'

export interface OverflowMenuItem {
  key: string
  label: string
  icon?: ReactNode
  onSelect: () => void
  disabled?: boolean
  /** Styled as a destructive action (e.g. Delete). */
  destructive?: boolean
  /** Draw a separator above this item. */
  separatorBefore?: boolean
}

interface OverflowMenuProps {
  items: OverflowMenuItem[]
  /** Accessible name for the trigger button. */
  label?: string
  /** Show a spinner on the trigger while a menu action is in flight. */
  busy?: boolean
  className?: string
}

const NAV_KEYS: MenuKey[] = ['ArrowDown', 'ArrowUp', 'Home', 'End']

export default function OverflowMenu({ items, label = 'More actions', busy = false, className }: OverflowMenuProps) {
  const [open, setOpen] = useState(false)
  const [focusIndex, setFocusIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([])
  const menuId = useId()

  const disabled = items.map((item) => Boolean(item.disabled))

  const openAt = (key: MenuKey) => {
    setFocusIndex(nextMenuIndex(disabled, -1, key))
    setOpen(true)
  }

  const close = (returnFocus: boolean) => {
    setOpen(false)
    setFocusIndex(-1)
    if (returnFocus) triggerRef.current?.focus()
  }

  // Move DOM focus to the active item.
  useEffect(() => {
    if (open && focusIndex >= 0) itemRefs.current[focusIndex]?.focus()
  }, [open, focusIndex])

  // Close on a pointer press outside the menu.
  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false)
        setFocusIndex(-1)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const onTriggerKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      openAt(e.key === 'ArrowDown' ? 'Home' : 'End')
    } else if (e.key === 'Escape' && open) {
      e.preventDefault()
      close(true)
    }
  }

  const onMenuKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((NAV_KEYS as string[]).includes(e.key)) {
      e.preventDefault()
      setFocusIndex((current) => nextMenuIndex(disabled, current, e.key as MenuKey))
    } else if (e.key === 'Escape') {
      e.preventDefault()
      close(true)
    } else if (e.key === 'Tab') {
      // Let focus move on naturally, but don't leave the menu hanging open.
      setOpen(false)
      setFocusIndex(-1)
    }
  }

  const select = (item: OverflowMenuItem) => {
    if (item.disabled) return
    close(true)
    item.onSelect()
  }

  return (
    <div ref={containerRef} className={clsx('relative', className)}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (open ? close(false) : openAt('Home'))}
        onKeyDown={onTriggerKeyDown}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={label}
        title={label}
        className={clsx('btn btn-ghost btn-icon text-sm', open && 'bg-augustus-800/50 text-augustus-100')}
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <MoreHorizontal className="w-5 h-5" />}
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={label}
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 top-full mt-2 z-30 w-56 max-w-[calc(100vw-2rem)] py-1.5 rounded-xl border border-augustus-800 bg-augustus-900 shadow-xl shadow-black/40"
        >
          {items.map((item, index) => (
            <div key={item.key}>
              {item.separatorBefore && (
                <div role="separator" className="my-1.5 border-t border-augustus-800" />
              )}
              <button
                ref={(el) => {
                  itemRefs.current[index] = el
                }}
                type="button"
                role="menuitem"
                tabIndex={-1}
                disabled={item.disabled}
                aria-disabled={item.disabled || undefined}
                onClick={() => select(item)}
                onMouseEnter={() => !item.disabled && setFocusIndex(index)}
                className={clsx(
                  'w-full min-h-[44px] px-3.5 py-2 flex items-center gap-3 text-left text-sm transition-colors',
                  'focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed',
                  item.destructive
                    ? 'text-red-400 hover:bg-red-500/10 focus:bg-red-500/10 hover:text-red-300 focus:text-red-300'
                    : 'text-augustus-200 hover:bg-augustus-800 focus:bg-augustus-800 hover:text-white focus:text-white'
                )}
              >
                {item.icon && <span className="flex-shrink-0 [&>svg]:w-4 [&>svg]:h-4">{item.icon}</span>}
                <span className="truncate">{item.label}</span>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
