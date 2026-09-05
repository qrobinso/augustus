export type ListeningRange = [number, number]

export interface PlaybackSample {
  mediaTime: number
  wallTimeMs: number
  playbackRate: number
  playing: boolean
  buffering?: boolean
}

export interface ListeningBatch {
  briefingId: string
  profileId: string
  ranges: ListeningRange[]
}

function responseStatus(error: unknown): number | undefined {
  if (!error || typeof error !== 'object' || !('response' in error)) return undefined
  const response = error.response
  if (!response || typeof response !== 'object' || !('status' in response)) return undefined
  return typeof response.status === 'number' ? response.status : undefined
}

/** Network errors, server errors, and explicitly transient client statuses retry. */
export function isRetryableListeningUploadError(error: unknown): boolean {
  const status = responseStatus(error)
  if (status === undefined || status >= 500) return true
  if (status >= 400 && status < 500) {
    return status === 408 || status === 425 || status === 429
  }
  return true
}

export function mergeListeningRanges(ranges: ListeningRange[]): ListeningRange[] {
  const ordered = ranges
    .filter(([start, end]) => Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start)
    .map(([start, end]): ListeningRange => [start, end])
    .sort((left, right) => left[0] - right[0])
  const merged: ListeningRange[] = []
  for (const [start, end] of ordered) {
    const previous = merged[merged.length - 1]
    if (previous && start <= previous[1]) {
      previous[1] = Math.max(previous[1], end)
    } else {
      merged.push([start, end])
    }
  }
  return merged
}

/**
 * Converts timeupdate samples into audio-time intervals only when media progress
 * agrees with elapsed wall time and playback rate.
 */
export class ContinuousPlaybackTracker {
  private previous: PlaybackSample | null = null
  private ranges: ListeningRange[] = []

  sample(sample: PlaybackSample): void {
    if (
      !sample.playing ||
      sample.buffering ||
      !Number.isFinite(sample.mediaTime) ||
      !Number.isFinite(sample.wallTimeMs) ||
      !Number.isFinite(sample.playbackRate) ||
      sample.mediaTime < 0 ||
      sample.playbackRate <= 0
    ) {
      this.previous = null
      return
    }

    const previous = this.previous
    this.previous = { ...sample }
    if (!previous) return

    const wallDelta = (sample.wallTimeMs - previous.wallTimeMs) / 1000
    const mediaDelta = sample.mediaTime - previous.mediaTime
    if (wallDelta <= 0 || mediaDelta <= 0) return

    const expectedMediaDelta = wallDelta * previous.playbackRate
    const tolerance = Math.max(0.35, expectedMediaDelta * 0.2)
    if (Math.abs(mediaDelta - expectedMediaDelta) > tolerance) return

    this.ranges = mergeListeningRanges([
      ...this.ranges,
      [previous.mediaTime, sample.mediaTime],
    ])
  }

  reset(): void {
    this.previous = null
  }

  drain(): ListeningRange[] {
    const drained = this.ranges
    this.ranges = []
    return drained
  }
}

/** Keeps failed uploads queued. Each immutable batch retains its source profile. */
export class ListeningCoverageUploader {
  private pending: ListeningBatch[] = []
  private flushing: Promise<boolean> | null = null

  constructor(private readonly upload: (batch: ListeningBatch) => Promise<unknown>) {}

  enqueue(batch: ListeningBatch): void {
    const ranges = mergeListeningRanges(batch.ranges)
    if (!batch.briefingId || !batch.profileId || ranges.length === 0) return
    this.pending.push({ ...batch, ranges })
  }

  get pendingCount(): number {
    return this.pending.length
  }

  flush(): Promise<boolean> {
    if (this.flushing) return this.flushing
    this.flushing = this.drainQueue().finally(() => {
      this.flushing = null
    })
    return this.flushing
  }

  private async drainQueue(): Promise<boolean> {
    while (this.pending.length > 0) {
      const batch = this.pending[0]
      try {
        await this.upload(batch)
      } catch (error) {
        if (isRetryableListeningUploadError(error)) return false
        this.pending.shift()
      }
      if (this.pending[0] === batch) this.pending.shift()
    }
    return true
  }
}
