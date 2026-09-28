// Pure keyboard-navigation helpers for OverflowMenu.

export type MenuKey = 'ArrowDown' | 'ArrowUp' | 'Home' | 'End'

/**
 * Index of the item that should receive focus after `key`, skipping disabled
 * items and wrapping at the ends. `current` of -1 means nothing is focused.
 * Returns -1 when every item is disabled.
 */
export function nextMenuIndex(disabled: boolean[], current: number, key: MenuKey): number {
  const count = disabled.length
  if (count === 0 || disabled.every(Boolean)) return -1

  const scan = (start: number, step: 1 | -1) => {
    for (let i = 0; i < count; i++) {
      const idx = (((start + step * i) % count) + count) % count
      if (!disabled[idx]) return idx
    }
    return -1
  }

  switch (key) {
    case 'Home':
      return scan(0, 1)
    case 'End':
      return scan(count - 1, -1)
    case 'ArrowDown':
      return scan(current < 0 ? 0 : current + 1, 1)
    case 'ArrowUp':
      return scan(current < 0 ? count - 1 : current - 1, -1)
  }
}
