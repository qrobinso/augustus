import { describe, expect, it } from 'vitest'
import type { Cast, ProviderInfo, VoiceOption } from '../api/client'
import {
  castCountHint,
  castPickerValue,
  isCastReadOnly,
  missingVoiceWarning,
  providerLabel,
  savedCastUnavailable,
  splitCastsByProvider,
  voiceChoice,
  voiceName,
} from './castProviders'

const cast = (id: string, tts_provider: string, is_default = false) =>
  ({ id, tts_provider, is_default, name: id, members: [] }) as unknown as Cast

const providers: ProviderInfo[] = [
  { id: 'gemini', label: 'Google Gemini', allows_custom_voice: false },
  { id: 'voicebox', label: 'Voicebox', allows_custom_voice: false },
]
const voices: VoiceOption[] = [{ id: 'vb-1', name: 'Dad' }, { id: 'vb-2', name: 'Kevin' }]

describe('castProviders', () => {
  it('labels known providers and passes unknown ids through', () => {
    expect(providerLabel(providers, 'voicebox')).toBe('Voicebox')
    expect(providerLabel(providers, 'mystery')).toBe('mystery')
  })

  it('splits casts into active and other providers, keeping order', () => {
    const { active, other } = splitCastsByProvider([cast('a', 'gemini'), cast('b', 'voicebox'), cast('c', 'gemini')], 'gemini')
    expect(active.map(c => c.id)).toEqual(['a', 'c'])
    expect(other.map(c => c.id)).toEqual(['b'])
  })

  it('classifies a member voice against the provider list', () => {
    expect(voiceChoice('', voices, false)).toEqual({ kind: 'empty' })
    expect(voiceChoice('vb-2', voices, false)).toEqual({ kind: 'listed', voice: voices[1] })
    expect(voiceChoice('af_heart:0.6', voices, true)).toEqual({ kind: 'custom' })
    expect(voiceChoice('Zephyr', voices, false)).toEqual({ kind: 'missing' })
  })

  it('shows voice names, falling back to the raw id', () => {
    expect(voiceName('vb-1', voices)).toBe('Dad')
    expect(voiceName('raw-id', voices)).toBe('raw-id')
  })

  it('explains how many casts the chosen provider has', () => {
    expect(castCountHint('Voicebox', 0)).toBe('No Voicebox casts yet. Create one before your next briefing.')
    expect(castCountHint('Google Gemini', 1)).toBe('1 Google Gemini cast')
    expect(castCountHint('Google Gemini', 3)).toBe('3 Google Gemini casts')
    expect(castCountHint('Piper', undefined)).toBe('')
  })

  it('flags a saved cast that is not among the active provider casts', () => {
    const casts = [cast('a', 'gemini', true), cast('b', 'gemini')]
    expect(savedCastUnavailable('b', casts)).toBe(false)
    expect(savedCastUnavailable('elevenlabs-cast', casts)).toBe(true)
    expect(savedCastUnavailable(undefined, casts)).toBe(false)
    expect(savedCastUnavailable(null, casts)).toBe(false)
  })

  it('shows the default cast in a picker when the selection is unavailable', () => {
    const casts = [cast('a', 'gemini'), cast('b', 'gemini', true)]
    expect(castPickerValue('a', casts)).toBe('a')
    expect(castPickerValue('elevenlabs-cast', casts)).toBe('b')
    expect(castPickerValue(undefined, casts)).toBe('b')
    expect(castPickerValue(undefined, [cast('a', 'gemini')])).toBe('')
  })

  it('keeps an existing cast read-only until the active provider is known and matches', () => {
    expect(isCastReadOnly(undefined, undefined)).toBe(false)
    expect(isCastReadOnly(undefined, 'gemini')).toBe(false)
    expect(isCastReadOnly(cast('a', 'gemini'), undefined)).toBe(true)
    expect(isCastReadOnly(cast('a', 'gemini'), '')).toBe(true)
    expect(isCastReadOnly(cast('a', 'elevenlabs'), 'gemini')).toBe(true)
    expect(isCastReadOnly(cast('a', 'gemini'), 'gemini')).toBe(false)
  })

  it('warns about a missing voice only once the voices have loaded', () => {
    const loaded = { provider: 'voicebox', provider_label: 'Voicebox', voices, allows_custom: false }
    expect(missingVoiceWarning('Zephyr', undefined, true)).toBeNull()
    expect(missingVoiceWarning('Zephyr', undefined, false)).toBeNull()
    expect(missingVoiceWarning('Zephyr', loaded, true)).toBeNull()
    expect(missingVoiceWarning('vb-1', loaded, false)).toBeNull()
    expect(missingVoiceWarning('Zephyr', loaded, false)).toBe("“Zephyr” isn't a Voicebox voice. Choose one from the list.")
  })
})
