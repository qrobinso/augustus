import { describe, it, expect } from 'vitest'
import {
  describeApiError,
  mergePendingSites,
  normalizeSiteUrl,
  partitionNewSites,
  readTopicPrompt,
} from './topicDraft'

describe('readTopicPrompt', () => {
  it('returns the trimmed prompt from router state', () => {
    expect(readTopicPrompt({ from: '/topics', prompt: '  EV batteries ' })).toBe('EV batteries')
  })

  it('returns null for missing, blank, or malformed state', () => {
    expect(readTopicPrompt(null)).toBeNull()
    expect(readTopicPrompt(undefined)).toBeNull()
    expect(readTopicPrompt({ from: '/topics' })).toBeNull()
    expect(readTopicPrompt({ prompt: '   ' })).toBeNull()
    expect(readTopicPrompt({ prompt: 42 })).toBeNull()
    expect(readTopicPrompt('prompt')).toBeNull()
  })
})

describe('normalizeSiteUrl', () => {
  it('lowercases, trims, and strips trailing slashes', () => {
    expect(normalizeSiteUrl('  https://Example.com/News/ ')).toBe('https://example.com/news')
  })
})

describe('mergePendingSites', () => {
  it('appends new sites and skips duplicates by normalized URL', () => {
    const existing = [{ name: 'A', url: 'https://a.com' }]
    const incoming = [
      { name: 'A again', url: 'https://A.com/' },
      { name: 'B', url: 'https://b.com' },
      { name: 'B dup', url: 'https://b.com/' },
      { name: 'Blank', url: '  ' },
    ]
    expect(mergePendingSites(existing, incoming)).toEqual([
      { name: 'A', url: 'https://a.com' },
      { name: 'B', url: 'https://b.com' },
    ])
  })

  it('does not mutate the existing list', () => {
    const existing = [{ name: 'A', url: 'https://a.com' }]
    mergePendingSites(existing, [{ name: 'B', url: 'https://b.com' }])
    expect(existing).toHaveLength(1)
  })
})

describe('partitionNewSites', () => {
  it('skips sites the user already follows and in-batch duplicates', () => {
    const sites = [
      { name: 'A', url: 'https://a.com' },
      { name: 'B', url: 'https://b.com/' },
      { name: 'B dup', url: 'https://B.com' },
    ]
    const { toCreate, skipped } = partitionNewSites(sites, ['https://a.com/'])
    expect(toCreate.map((s) => s.name)).toEqual(['B'])
    expect(skipped.map((s) => s.name)).toEqual(['A', 'B dup'])
  })
})

describe('describeApiError', () => {
  it('prefers the API detail message', () => {
    const err = Object.assign(new Error('Request failed'), { response: { data: { detail: 'No AI provider' } } })
    expect(describeApiError(err, 'fallback')).toBe('No AI provider')
  })

  it('falls back to the error message, then the fallback', () => {
    expect(describeApiError(new Error('boom'), 'fallback')).toBe('boom')
    expect(describeApiError(null, 'fallback')).toBe('fallback')
  })
})
