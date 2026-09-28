import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DashboardGenerate, { briefingSummary, durationChoices, filterTopics, trackAcceptedBriefing } from './DashboardGenerate'
import { useStore } from '../store/useStore'
import { api, briefingsApi, type Briefing, type Profile } from '../api/client'

vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  })
})

// Static rendering has no store subscription; read the real store's current snapshot.
vi.mock('../store/useStore', async importOriginal => {
  const actual = await importOriginal<typeof import('../store/useStore')>()
  return { useStore: Object.assign(
    (selector: (state: ReturnType<typeof actual.useStore.getState>) => unknown) => selector(actual.useStore.getState()),
    actual.useStore,
  ) }
})

beforeEach(() => {
  useStore.setState({ currentProfile: { id: 'profile-1', name: 'Profile' } as Profile })
})

function renderQueue(briefings: Briefing[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(['briefings', 'queue', 'profile-1'], { briefings, total: briefings.length })
  client.setQueryData(['topics'], { topics: [] })
  client.setQueryData(['casts'], { casts: [] })
  return renderToStaticMarkup(
    createElement(StaticRouter, { location: '/profile/generate' },
      createElement(QueryClientProvider, { client }, createElement(DashboardGenerate)))
  )
}

describe('generation queue display', () => {
  it('shows all queued jobs beyond a history page and keeps another request available', () => {
    const briefings = Array.from({ length: 12 }, (_, index): Briefing => ({
      id: `job-${index}`, user_id: 'user', title: `Podcast ${index + 1}`,
      status: index === 0 ? 'generating' : 'queued', created_at: '',
      listened: false, favorite: false, sources: [], extra_data: {},
    }))
    const markup = renderQueue(briefings)
    for (let index = 1; index <= 12; index++) {
      expect(markup).toContain(`aria-label="Cancel Podcast ${index}"`)
    }
    expect(markup).toContain('Generating briefing')
    expect(markup).toContain('Queued for generation')
    expect(markup).toContain('Queue another briefing')
    expect(markup).not.toContain('disabled=""')
  })

  it('offers creation when no work is queued', () => {
    const markup = renderQueue([])
    expect(markup).toContain('Create briefing')
    expect(markup).not.toContain('aria-label="Generation queue"')
  })
})


describe('generation request ownership', () => {
  it('deduplicates an accepted job already observed by the queue poll', () => {
    const tracked = { profileId: 'profile-1', ids: ['job-1'] }
    expect(trackAcceptedBriefing(tracked, 'job-1', 'profile-1', 'profile-1').ids).toEqual(['job-1'])
    expect(trackAcceptedBriefing(tracked, 'job-2', 'profile-1', 'profile-1').ids).toEqual(['job-1', 'job-2'])
  })

  it('ignores an old request after switching profile', () => {
    const tracked = { profileId: 'profile-2', ids: ['current-job'] }
    expect(trackAcceptedBriefing(tracked, 'old-job', 'profile-1', 'profile-2')).toBe(tracked)
  })

  it('keeps generation and cancellation bound to their requested profile at transport time', async () => {
    const originalAdapter = api.defaults.adapter
    const requests: Array<{ url?: string; profileId: unknown }> = []
    api.defaults.adapter = async config => {
      requests.push({ url: config.url, profileId: config.headers['X-Profile-ID'] })
      return { data: { id: 'job-1' }, status: 202, statusText: 'Accepted', headers: {}, config }
    }
    try {
      useStore.setState({ currentProfile: { id: 'profile-2' } as Profile })
      await briefingsApi.generate({}, 'profile-1')
      await briefingsApi.cancel('job-1', 'profile-1')
      expect(requests).toEqual([
        { url: '/api/briefings/generate', profileId: 'profile-1' },
        { url: '/api/briefings/job-1/cancel', profileId: 'profile-1' },
      ])
    } finally {
      api.defaults.adapter = originalAdapter
    }
  })
})


describe('new briefing form helpers', () => {
  it('offers the configured default length alongside the presets', () => {
    expect(durationChoices(10)).toEqual([5, 10, 15, 20, 30])
    expect(durationChoices(12)).toEqual([5, 10, 12, 15, 20, 30])
    expect(durationChoices(undefined)).toEqual([5, 10, 15, 20, 30])
  })

  it('summarizes what will be generated', () => {
    expect(briefingSummary({ mode: 'existing', selectedTopicNames: [], durationMinutes: 10 })).toBe('10 min · All topics')
    expect(briefingSummary({ mode: 'existing', selectedTopicNames: ['AI', 'EVs'], durationMinutes: 5, castName: 'Morning Crew' }))
      .toBe('5 min · AI & EVs · Morning Crew')
    expect(briefingSummary({ mode: 'existing', selectedTopicNames: ['A', 'B', 'C'] })).toBe('3 topics')
    expect(briefingSummary({ mode: 'new', selectedTopicNames: ['ignored'], durationMinutes: 15 })).toBe('15 min · New topic')
  })

  it('filters topics by name but keeps selected ones visible', () => {
    const topics = [{ id: '1', name: 'NFL' }, { id: '2', name: 'Android Gaming' }, { id: '3', name: 'Retro gaming' }]
    expect(filterTopics(topics, '', []).map(t => t.id)).toEqual(['1', '2', '3'])
    expect(filterTopics(topics, 'GAMING', []).map(t => t.id)).toEqual(['2', '3'])
    expect(filterTopics(topics, 'gaming', ['1']).map(t => t.id)).toEqual(['1', '2', '3'])
  })
})
