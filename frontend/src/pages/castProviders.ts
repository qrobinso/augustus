import type { Cast, ProviderInfo, VoiceOption } from '../api/client'

/** Select value that reveals the free-text voice ID input. */
export const CUSTOM_VOICE = '__custom__'

export function providerLabel(providers: ProviderInfo[], id: string): string {
  return providers.find(p => p.id === id)?.label ?? id
}

export function splitCastsByProvider(casts: Cast[], activeProvider: string): { active: Cast[]; other: Cast[] } {
  return {
    active: casts.filter(c => c.tts_provider === activeProvider),
    other: casts.filter(c => c.tts_provider !== activeProvider),
  }
}

export type VoiceChoice =
  | { kind: 'empty' }
  | { kind: 'listed'; voice: VoiceOption }
  | { kind: 'custom' }
  | { kind: 'missing' }

/** How a member's saved voice relates to the provider's voice list. */
export function voiceChoice(voiceId: string, voices: VoiceOption[], allowsCustom: boolean): VoiceChoice {
  if (!voiceId.trim()) return { kind: 'empty' }
  const voice = voices.find(v => v.id === voiceId)
  if (voice) return { kind: 'listed', voice }
  return allowsCustom ? { kind: 'custom' } : { kind: 'missing' }
}

export function voiceName(voiceId: string, voices: VoiceOption[]): string {
  return voices.find(v => v.id === voiceId)?.name ?? voiceId
}

export function castCountHint(label: string, count: number | undefined): string {
  if (count === undefined) return ''
  if (count === 0) return `No ${label} casts yet. Create one before your next briefing.`
  return `${count} ${label} cast${count === 1 ? '' : 's'}`
}

/**
 * True when a saved cast (e.g. a schedule's) isn't among the active provider's
 * casts, so generation will fall back to that provider's default cast.
 */
export function savedCastUnavailable(castId: string | null | undefined, casts: Cast[]): boolean {
  return !!castId && !casts.some(c => c.id === castId)
}

/** The cast a picker should show: the selection if it's listed, else the default. */
export function castPickerValue(castId: string | null | undefined, casts: Cast[]): string {
  if (castId && casts.some(c => c.id === castId)) return castId
  return casts.find(c => c.is_default)?.id ?? ''
}

/**
 * An existing cast is editable only once the active provider is known and matches it.
 * New casts (no cast yet) are never read-only: they take the active provider on save.
 */
export function isCastReadOnly(cast: Pick<Cast, 'tts_provider'> | undefined, activeProvider: string | undefined): boolean {
  if (!cast) return false
  return !activeProvider || cast.tts_provider !== activeProvider
}
