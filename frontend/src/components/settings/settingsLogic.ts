import type { ModelOption } from '../../api/client'

/** Page sections reachable from the Settings jump bar, in display order. */
export const SETTINGS_GROUPS = [
  { id: 'settings-ai-voice', label: 'AI & voice' },
  { id: 'settings-content', label: 'Content' },
  { id: 'settings-app', label: 'App' },
] as const

export type SettingsGroupId = (typeof SETTINGS_GROUPS)[number]['id']

// Duration slider values: 1 = Short (3 min), 2 = Medium (7 min), 3 = Long (25 min)
export function durationToSlider(minutes: number): number {
  if (minutes <= 5) return 1
  if (minutes <= 15) return 2
  return 3
}

export function sliderToDuration(sliderValue: number): number {
  switch (sliderValue) {
    case 1: return 3
    case 2: return 7
    case 3: return 25
    default: return 7
  }
}

export function getDurationLabel(sliderValue: number): string {
  switch (sliderValue) {
    case 1: return 'Short (3 min)'
    case 2: return 'Medium (7 min)'
    case 3: return 'Long (25 min)'
    default: return 'Medium (7 min)'
  }
}

const COMPLEXITY_LABELS: Record<number, string> = {
  1: 'Casual',
  2: 'Accessible',
  3: 'Standard',
  4: 'Advanced',
  5: 'Expert',
}

/** Label for a 1–5 conversation complexity level; empty for anything else. */
export function getComplexityLabel(level: number): string {
  return COMPLEXITY_LABELS[level] ?? ''
}

/** Short context-window label, e.g. 128000 -> "128K", 1048576 -> "1.0M". */
export function formatContextLength(length?: number): string {
  if (!length) return ''
  if (length >= 1000000) return `${(length / 1000000).toFixed(1)}M`
  if (length >= 1000) return `${(length / 1000).toFixed(0)}K`
  return length.toString()
}

/** Case-insensitive match on model name, provider, or id. A blank search keeps every model. */
export function filterModels(models: ModelOption[], search: string): ModelOption[] {
  if (!search.trim()) return models
  const needle = search.toLowerCase()
  return models.filter(model =>
    model.name.toLowerCase().includes(needle) ||
    model.provider.toLowerCase().includes(needle) ||
    model.id.toLowerCase().includes(needle)
  )
}

/** Groups models by provider, preserving the order models first appear in. */
export function groupModelsByProvider(models: ModelOption[]): Record<string, ModelOption[]> {
  const groups: Record<string, ModelOption[]> = {}
  for (const model of models) {
    if (!groups[model.provider]) {
      groups[model.provider] = []
    }
    groups[model.provider].push(model)
  }
  return groups
}
