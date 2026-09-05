import { describe, expect, it } from 'vitest'
import {
  ContinuousPlaybackTracker,
  ListeningCoverageUploader,
  mergeListeningRanges,
} from './listeningCoverage'

describe('mergeListeningRanges', () => {
  it('unions overlaps and repeated intervals', () => {
    expect(mergeListeningRanges([[20, 60], [0, 40], [0, 40]])).toEqual([[0, 60]])
  })
})

describe('ContinuousPlaybackTracker', () => {
  it('does not count a seek gap', () => {
    const tracker = new ContinuousPlaybackTracker()
    tracker.sample({ mediaTime: 0, wallTimeMs: 0, playbackRate: 1, playing: true })
    tracker.sample({ mediaTime: 1, wallTimeMs: 1000, playbackRate: 1, playing: true })
    tracker.sample({ mediaTime: 50, wallTimeMs: 2000, playbackRate: 1, playing: true })
    tracker.sample({ mediaTime: 51, wallTimeMs: 3000, playbackRate: 1, playing: true })

    expect(tracker.drain()).toEqual([[0, 1], [50, 51]])
  })

  it('resets around pauses and buffering', () => {
    const tracker = new ContinuousPlaybackTracker()
    tracker.sample({ mediaTime: 0, wallTimeMs: 0, playbackRate: 1, playing: true })
    tracker.sample({ mediaTime: 2, wallTimeMs: 2000, playbackRate: 1, playing: true })
    tracker.sample({ mediaTime: 2, wallTimeMs: 12000, playbackRate: 1, playing: false })
    tracker.sample({ mediaTime: 2, wallTimeMs: 13000, playbackRate: 1, playing: true, buffering: true })
    tracker.sample({ mediaTime: 20, wallTimeMs: 14000, playbackRate: 1, playing: true })
    tracker.sample({ mediaTime: 21, wallTimeMs: 15000, playbackRate: 1, playing: true })

    expect(tracker.drain()).toEqual([[0, 2], [20, 21]])
  })

  it('accepts two-times playback and unions listened time after a rewind', () => {
    const tracker = new ContinuousPlaybackTracker()
    tracker.sample({ mediaTime: 0, wallTimeMs: 0, playbackRate: 2, playing: true })
    tracker.sample({ mediaTime: 4, wallTimeMs: 2000, playbackRate: 2, playing: true })
    tracker.sample({ mediaTime: 1, wallTimeMs: 3000, playbackRate: 2, playing: true })
    tracker.sample({ mediaTime: 3, wallTimeMs: 4000, playbackRate: 2, playing: true })

    expect(tracker.drain()).toEqual([[0, 4]])
  })
})

describe('ListeningCoverageUploader', () => {
  it('retries a failed batch with the profile captured when it was queued', async () => {
    const calls: Array<{ briefingId: string; profileId: string; ranges: number[][] }> = []
    let fail = true
    const uploader = new ListeningCoverageUploader(async batch => {
      calls.push(batch)
      if (fail) throw new Error('offline')
    })
    uploader.enqueue({
      briefingId: 'briefing-1',
      profileId: 'source-profile',
      ranges: [[0, 5]],
    })

    expect(await uploader.flush()).toBe(false)
    expect(uploader.pendingCount).toBe(1)
    fail = false
    expect(await uploader.flush()).toBe(true)

    expect(uploader.pendingCount).toBe(0)
    expect(calls).toEqual([
      { briefingId: 'briefing-1', profileId: 'source-profile', ranges: [[0, 5]] },
      { briefingId: 'briefing-1', profileId: 'source-profile', ranges: [[0, 5]] },
    ])
  })

  it.each([404, 422])('discards terminal HTTP %s and continues with the next profile batch', async status => {
    const calls: string[] = []
    const uploader = new ListeningCoverageUploader(async batch => {
      calls.push(`${batch.briefingId}:${batch.profileId}`)
      if (batch.briefingId === 'deleted') {
        throw Object.assign(new Error('terminal'), { response: { status } })
      }
    })
    uploader.enqueue({ briefingId: 'deleted', profileId: 'profile-a', ranges: [[0, 5]] })
    uploader.enqueue({ briefingId: 'current', profileId: 'profile-b', ranges: [[10, 15]] })

    expect(await uploader.flush()).toBe(true)

    expect(uploader.pendingCount).toBe(0)
    expect(calls).toEqual(['deleted:profile-a', 'current:profile-b'])
  })

  it('keeps a server-failed batch for retry before later batches', async () => {
    const calls: string[] = []
    let serverAvailable = false
    const uploader = new ListeningCoverageUploader(async batch => {
      calls.push(`${batch.briefingId}:${batch.profileId}`)
      if (batch.briefingId === 'first' && !serverAvailable) {
        throw Object.assign(new Error('server error'), { response: { status: 500 } })
      }
    })
    uploader.enqueue({ briefingId: 'first', profileId: 'profile-a', ranges: [[0, 5]] })
    uploader.enqueue({ briefingId: 'second', profileId: 'profile-b', ranges: [[10, 15]] })

    expect(await uploader.flush()).toBe(false)
    expect(uploader.pendingCount).toBe(2)
    serverAvailable = true
    expect(await uploader.flush()).toBe(true)

    expect(uploader.pendingCount).toBe(0)
    expect(calls).toEqual([
      'first:profile-a',
      'first:profile-a',
      'second:profile-b',
    ])
  })
})
