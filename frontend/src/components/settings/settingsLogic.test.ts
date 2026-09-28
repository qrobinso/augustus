import { describe, expect, it } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import type { ModelOption } from '../../api/client'
import {
  SETTINGS_GROUPS,
  apiErrorMessage,
  durationToSlider,
  filterModels,
  flushPendingSave,
  formatContextLength,
  getComplexityLabel,
  getDurationLabel,
  groupModelsByProvider,
  isServerUrl,
  sliderToDuration,
  ttsProviderUpdate,
  voiceboxUrlUpdate,
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

describe('voicebox settings logic', () => {
  it('accepts only http(s) server URLs', () => {
    expect(isServerUrl('http://192.168.4.44:17493')).toBe(true)
    expect(isServerUrl('https://voicebox.home')).toBe(true)
    expect(isServerUrl('')).toBe(false)
    expect(isServerUrl('192.168.4.44:17493')).toBe(false)
    expect(isServerUrl('ftp://x')).toBe(false)
  })

  it('holds back switching to Voicebox until a URL is set', () => {
    expect(ttsProviderUpdate('voicebox', 'gemini', '')).toBeNull()
    expect(ttsProviderUpdate('voicebox', 'gemini', 'http://vb:17493')).toBe('voicebox')
    expect(ttsProviderUpdate('gemini', 'gemini', '')).toBeNull()      // unchanged
    expect(ttsProviderUpdate('piper', 'voicebox', '')).toBe('piper')
  })
})

describe('voiceboxUrlUpdate', () => {
  it('sends a changed, valid URL trimmed', () => {
    expect(voiceboxUrlUpdate(' http://vb:17493 ', null, 'voicebox')).toBe('http://vb:17493')
    expect(voiceboxUrlUpdate('http://new:17493', 'http://old:17493', 'piper')).toBe('http://new:17493')
  })

  it('sends nothing when the URL is unchanged or only differs by whitespace', () => {
    expect(voiceboxUrlUpdate('http://vb:17493', 'http://vb:17493', 'voicebox')).toBeNull()
    expect(voiceboxUrlUpdate('http://vb:17493  ', 'http://vb:17493', 'voicebox')).toBeNull()
    expect(voiceboxUrlUpdate('', null, 'gemini')).toBeNull()
    expect(voiceboxUrlUpdate('', undefined, 'voicebox')).toBeNull()
  })

  it('holds back an incomplete URL', () => {
    expect(voiceboxUrlUpdate('192.168.4.44', 'http://vb:17493', 'piper')).toBeNull()
  })

  it('clears the URL only once Voicebox is no longer the selected provider', () => {
    expect(voiceboxUrlUpdate('', 'http://vb:17493', 'voicebox')).toBeNull()
    expect(voiceboxUrlUpdate('   ', 'http://vb:17493', 'voicebox')).toBeNull()
    expect(voiceboxUrlUpdate('', 'http://vb:17493', 'piper')).toBe('')
  })
})

describe('apiErrorMessage', () => {
  it("prefers the API's detail", () => {
    const error = new AxiosError('Request failed with status code 400', '400', undefined, undefined, {
      data: { detail: 'Set a Voicebox URL before choosing Voicebox.' },
      status: 400,
    } as AxiosResponse)
    expect(apiErrorMessage(error)).toBe('Set a Voicebox URL before choosing Voicebox.')
  })

  it('falls back to the error message, then a generic message', () => {
    expect(apiErrorMessage(new Error('Network Error'))).toBe('Network Error')
    expect(apiErrorMessage('nope')).toBe('Something went wrong. Try again.')
  })
})

describe('flushPendingSave', () => {
  it('cancels the debounced auto-save and saves now', () => {
    const calls: string[] = []
    const timer = setTimeout(() => calls.push('debounced'), 0)
    const ref: { current?: ReturnType<typeof setTimeout> } = { current: timer }
    flushPendingSave(ref, () => calls.push('save'))
    expect(calls).toEqual(['save'])
    expect(ref.current).toBeUndefined()
    return new Promise<void>(resolve => setTimeout(() => {
      expect(calls).toEqual(['save'])  // the debounced save never fires as well
      resolve()
    }, 5))
  })
})
