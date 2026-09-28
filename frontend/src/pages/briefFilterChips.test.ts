import { describe, it, expect } from 'vitest'
import { statusChipLabel, castChipLabel, topicsChipLabel } from './briefFilterChips'

describe('brief filter chip labels', () => {
  it('shows the default label when a filter is unset', () => {
    expect(statusChipLabel(undefined)).toBe('Status')
    expect(castChipLabel(undefined, [])).toBe('All Casts')
    expect(topicsChipLabel([], [])).toBe('All Topics')
  })

  it('shows the active listened status', () => {
    expect(statusChipLabel(true)).toBe('Listened')
    expect(statusChipLabel(false)).toBe('Not Listened')
  })

  it('shows the selected cast name, falling back when it is unknown', () => {
    const casts = [{ id: 'c1', name: 'Morning Crew' }]
    expect(castChipLabel('c1', casts)).toBe('Morning Crew')
    expect(castChipLabel('gone', casts)).toBe('Cast')
  })

  it('names a single topic and counts several', () => {
    const topics = [
      { id: 't1', name: 'AI' },
      { id: 't2', name: 'Markets' },
    ]
    expect(topicsChipLabel(['t2'], topics)).toBe('Markets')
    expect(topicsChipLabel(['missing'], topics)).toBe('1 topic')
    expect(topicsChipLabel(['t1', 't2'], topics)).toBe('2 topics')
  })
})
