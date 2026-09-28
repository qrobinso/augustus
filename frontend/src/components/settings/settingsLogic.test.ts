import { describe, expect, it } from 'vitest'
import type { ModelOption } from '../../api/client'
import {
  SETTINGS_GROUPS,
  durationToSlider,
  filterModels,
  formatContextLength,
  getComplexityLabel,
  getDurationLabel,
  groupModelsByProvider,
  sliderToDuration,
} from './settingsLogic'

const models: ModelOption[] = [
  { id: 'anthropic/claude-sonnet', name: 'Claude Sonnet', provider: 'Anthropic', context_length: 200000 },
  { id: 'openai/gpt-5', name: 'GPT-5', provider: 'OpenAI' },
  { id: 'anthropic/claude-haiku', name: 'Claude Haiku', provider: 'Anthropic' },
]

describe('settings jump groups', () => {
  it('lists the three groups in page order with unique ids', () => {
    expect(SETTINGS_GROUPS.map(g => g.label)).toEqual(['AI & voice', 'Content', 'App'])
    expect(new Set(SETTINGS_GROUPS.map(g => g.id)).size).toBe(SETTINGS_GROUPS.length)
  })
})

describe('briefing duration slider', () => {
  it('maps stored minutes onto the three slider stops', () => {
    expect(durationToSlider(3)).toBe(1)
    expect(durationToSlider(5)).toBe(1)
    expect(durationToSlider(6)).toBe(2)
    expect(durationToSlider(15)).toBe(2)
    expect(durationToSlider(16)).toBe(3)
    expect(durationToSlider(25)).toBe(3)
  })

  it('round-trips every slider stop', () => {
    for (const stop of [1, 2, 3]) {
      expect(durationToSlider(sliderToDuration(stop))).toBe(stop)
    }
  })

  it('falls back to medium for unknown stops', () => {
    expect(sliderToDuration(9)).toBe(7)
    expect(getDurationLabel(9)).toBe('Medium (7 min)')
    expect(getDurationLabel(3)).toBe('Long (25 min)')
  })
})

describe('conversation complexity label', () => {
  it('names each level and leaves out-of-range values blank', () => {
    expect([1, 2, 3, 4, 5].map(getComplexityLabel)).toEqual(['Casual', 'Accessible', 'Standard', 'Advanced', 'Expert'])
    expect(getComplexityLabel(0)).toBe('')
    expect(getComplexityLabel(6)).toBe('')
  })
})

describe('model picker helpers', () => {
  it('formats context lengths', () => {
    expect(formatContextLength(undefined)).toBe('')
    expect(formatContextLength(512)).toBe('512')
    expect(formatContextLength(128000)).toBe('128K')
    expect(formatContextLength(1048576)).toBe('1.0M')
  })

  it('filters case-insensitively by name, provider, or id and ignores blank searches', () => {
    expect(filterModels(models, '   ')).toBe(models)
    expect(filterModels(models, 'HAIKU').map(m => m.id)).toEqual(['anthropic/claude-haiku'])
    expect(filterModels(models, 'openai').map(m => m.id)).toEqual(['openai/gpt-5'])
    expect(filterModels(models, 'anthropic/').length).toBe(2)
  })

  it('groups by provider in first-seen order', () => {
    const grouped = groupModelsByProvider(models)
    expect(Object.keys(grouped)).toEqual(['Anthropic', 'OpenAI'])
    expect(grouped.Anthropic.map(m => m.id)).toEqual(['anthropic/claude-sonnet', 'anthropic/claude-haiku'])
  })
})
