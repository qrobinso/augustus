import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { useStore } from '../store/useStore'
import { audioManager } from '../utils/audioManager'
import { briefingsApi, type Briefing, type Profile } from '../api/client'
import { startPlayerBreakout, refreshQueuedBreakouts } from './playerBreakout'

// Browser storage boundary; the real persisted store and queue actions run below.
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  })
})

const source: Briefing = {
  id: 'source', user_id: 'user', title: 'Daily briefing', status: 'completed',
  created_at: '', listened: false, favorite: false, sources: [], extra_data: {},
  chapters: [{ title: 'Solar power', start_time: 0 }, { title: 'Grid storage', start_time: 30 }],
}
const generated: Briefing = { ...source, id: 'deep-dive', title: 'Grid storage: deep dive', status: 'queued' }
const later = { id: 'later', type: 'briefing' as const, title: 'Later', audioUrl: '/later.mp3' }

beforeEach(() => {
  vi.spyOn(audioManager, 'setSourceAndPlay').mockResolvedValue()
  vi.spyOn(audioManager, 'pause').mockImplementation(() => {})
  useStore.setState({
    currentProfile: { id: 'profile-1' } as Profile,
    currentAudio: { id: 'source', type: 'briefing', title: 'Daily briefing', audioUrl: '/source.mp3' },
    currentTime: 42, isPlaying: true, queue: [later], waitingForQueue: false, queueFallbackSourceId: null,
  })
})
afterEach(() => { vi.restoreAllMocks() })

describe('one-click player breakout', () => {
  it('captures the current chapter, reserves play-next, and does not interrupt playback', async () => {
    let accept!: (value: Briefing) => void
    const generate = vi.spyOn(briefingsApi, 'generateBreakout').mockImplementation(() => new Promise(resolve => { accept = resolve }))
    const request = startPlayerBreakout(source, 42)
    expect(useStore.getState().queue[0].breakout?.status).toBe('requesting')
    expect(generate).toHaveBeenCalledWith({ source_briefing_id: 'source', chapter_index: 1, max_duration_minutes: 10 }, 'profile-1')
    // A later seek cannot change the submitted subject.
    useStore.setState({ currentTime: 5 })
    accept(generated)
    await request
    expect(useStore.getState().queue.map(item => item.id)).toEqual(['deep-dive', 'later'])
    expect(useStore.getState().currentAudio?.id).toBe('source')
    expect(useStore.getState().isPlaying).toBe(true)
    expect(audioManager.setSourceAndPlay).not.toHaveBeenCalled()
  })

  it('deduplicates repeat clicks for the same chapter', async () => {
    const generate = vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await Promise.all([startPlayerBreakout(source, 42), startPlayerBreakout(source, 43)])
    expect(generate).toHaveBeenCalledTimes(1)
    expect(useStore.getState().queue).toHaveLength(2)
  })

  it('waits at the end, then automatically plays the deep dive before other queued audio', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    useStore.setState({ isPlaying: false })
    expect(useStore.getState().playFromQueueHead()).toBe(true)
    expect(useStore.getState().waitingForQueue).toBe(true)
    expect(audioManager.setSourceAndPlay).not.toHaveBeenCalled()
    const get = vi.spyOn(briefingsApi, 'get').mockResolvedValue({ ...generated, status: 'completed', audio_url: '/deep.mp3' })
    await refreshQueuedBreakouts()
    expect(get).toHaveBeenCalledWith('deep-dive', 'profile-1')
    expect(useStore.getState().currentAudio?.id).toBe('deep-dive')
    expect(useStore.getState().queue.map(item => item.id)).toEqual(['later'])
    expect(audioManager.setSourceAndPlay).toHaveBeenCalledWith('/deep.mp3', true)
  })

  it('fills the reserved slot when ready without starting over the current episode', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    vi.spyOn(briefingsApi, 'get').mockResolvedValue({ ...generated, status: 'completed', audio_url: '/deep.mp3' })
    await refreshQueuedBreakouts()
    expect(useStore.getState().queue[0].audioUrl).toBe('/deep.mp3')
    expect(useStore.getState().currentAudio?.id).toBe('source')
    expect(audioManager.setSourceAndPlay).not.toHaveBeenCalled()
  })

  it('does not reinsert an item removed while generation is in progress', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    let finish!: (value: Briefing) => void
    vi.spyOn(briefingsApi, 'get').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const refresh = refreshQueuedBreakouts()
    useStore.getState().removeFromQueue('deep-dive')
    finish({ ...generated, status: 'completed', audio_url: '/deep.mp3' })
    await refresh
    expect(useStore.getState().queue.map(item => item.id)).toEqual(['later'])
  })

  it('marks generation failure and lets the next playable item proceed', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    useStore.setState({ isPlaying: false })
    useStore.getState().playFromQueueHead()
    vi.spyOn(briefingsApi, 'get').mockResolvedValue({ ...generated, status: 'failed', error_message: 'Research failed' })
    await refreshQueuedBreakouts()
    expect(useStore.getState().currentAudio?.id).toBe('later')
    expect(useStore.getState().queue[0].breakout?.error).toBe('Research failed')
  })

  it('requests the normal autoplay fallback if a waiting generation fails with no later queue item', async () => {
    useStore.setState({ queue: [] })
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    useStore.setState({ isPlaying: false })
    useStore.getState().playFromQueueHead()
    vi.spyOn(briefingsApi, 'get').mockResolvedValue({ ...generated, status: 'cancelled' })
    await refreshQueuedBreakouts()
    expect(useStore.getState().waitingForQueue).toBe(false)
    expect(useStore.getState().queueFallbackSourceId).toBe('source')
    expect(audioManager.setSourceAndPlay).not.toHaveBeenCalled()
  })

  it('preserves pending work on a transient polling failure', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    vi.spyOn(briefingsApi, 'get').mockRejectedValue(new Error('Offline'))
    await refreshQueuedBreakouts()
    expect(useStore.getState().queue[0].breakout?.status).toBe('generating')
  })

  it('keeps the latest request intact if an older removed request resolves late', async () => {
    const replies: Array<(value: Briefing) => void> = []
    vi.spyOn(briefingsApi, 'generateBreakout').mockImplementation(() => new Promise(resolve => replies.push(resolve)))
    const first = startPlayerBreakout(source, 42)
    useStore.getState().removeFromQueue(useStore.getState().queue[0].id)
    const second = startPlayerBreakout(source, 42)
    replies[0]({ ...generated, id: 'old-request' })
    await first
    expect(useStore.getState().queue[0].breakout?.status).toBe('requesting')
    replies[1]({ ...generated, id: 'new-request' })
    await second
    expect(useStore.getState().queue.map(item => item.id)).toEqual(['new-request', 'later'])
  })

  it('does not overlap polls for the same reservation', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    let finish!: (value: Briefing) => void
    const get = vi.spyOn(briefingsApi, 'get').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const first = refreshQueuedBreakouts()
    const second = refreshQueuedBreakouts()
    expect(get).toHaveBeenCalledTimes(1)
    finish({ ...generated, status: 'completed', audio_url: '/deep.mp3' })
    await Promise.all([first, second])
  })

  it('marks rejected requests clearly and allows a later retry', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockRejectedValueOnce(new Error('Generation busy')).mockResolvedValue(generated)
    await expect(startPlayerBreakout(source, 42)).rejects.toThrow('Generation busy')
    expect(useStore.getState().queue[0].breakout?.error).toBe('Generation busy')
    await startPlayerBreakout(source, 42)
    expect(useStore.getState().queue[0].id).toBe('deep-dive')
  })

  it('clearing the queue while waiting prevents a late completion from playing', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    useStore.getState().playFromQueueHead()
    let finish!: (value: Briefing) => void
    vi.spyOn(briefingsApi, 'get').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const refresh = refreshQueuedBreakouts()
    useStore.getState().clearQueue()
    finish({ ...generated, status: 'completed', audio_url: '/deep.mp3' })
    await refresh
    expect(useStore.getState().queue).toEqual([])
    expect(useStore.getState().waitingForQueue).toBe(false)
    expect(audioManager.setSourceAndPlay).not.toHaveBeenCalled()
  })

  it('restores accepted generation jobs after reload without resubmitting them', async () => {
    const generate = vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    const persisted = localStorage.getItem('augustus-profile-storage')!
    useStore.setState({ queue: [] })
    localStorage.setItem('augustus-profile-storage', persisted)
    await useStore.persist.rehydrate()
    expect(useStore.getState().queue[0].breakout?.status).toBe('generating')
    vi.spyOn(briefingsApi, 'get').mockResolvedValue({ ...generated, status: 'completed', audio_url: '/deep.mp3' })
    await refreshQueuedBreakouts()
    expect(useStore.getState().queue[0].audioUrl).toBe('/deep.mp3')
    expect(generate).toHaveBeenCalledTimes(1)
    expect(audioManager.setSourceAndPlay).not.toHaveBeenCalled()
  })

  it('does not autoplay a completion after the user changes profile', async () => {
    vi.spyOn(briefingsApi, 'generateBreakout').mockResolvedValue(generated)
    await startPlayerBreakout(source, 42)
    useStore.getState().playFromQueueHead()
    let finish!: (value: Briefing) => void
    vi.spyOn(briefingsApi, 'get').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const refresh = refreshQueuedBreakouts()
    useStore.getState().setCurrentProfile({ id: 'profile-2' } as Profile)
    finish({ ...generated, status: 'completed', audio_url: '/deep.mp3' })
    await refresh
    expect(useStore.getState().waitingForQueue).toBe(false)
    expect(audioManager.setSourceAndPlay).not.toHaveBeenCalled()
  })

  it('rejects a stale source or unknown current topic without generating', async () => {
    const generate = vi.spyOn(briefingsApi, 'generateBreakout')
    await expect(startPlayerBreakout({ ...source, id: 'other' }, 42)).rejects.toThrow()
    await expect(startPlayerBreakout({ ...source, chapters: [] }, 42)).rejects.toThrow()
    expect(generate).not.toHaveBeenCalled()
    expect(useStore.getState().queue).toEqual([later])
  })
})
