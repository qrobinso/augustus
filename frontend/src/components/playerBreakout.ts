import axios from 'axios'
import { briefingsApi, type Briefing } from '../api/client'
import { useStore } from '../store/useStore'
import type { QueueItem } from '../store/queue'
import { findActiveChapterIndex } from './breakout'

let requestSequence = 0
const polling = new Set<string>()

export function breakoutError(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string') {
    return error.response.data.detail
  }
  return error instanceof Error ? error.message : 'Could not create the deep dive. Try again.'
}

function applyBriefing(item: QueueItem, briefing: Briefing): QueueItem {
  const failed = briefing.status === 'failed' || briefing.status === 'cancelled' ||
    (briefing.status === 'completed' && !briefing.audio_url)
  return {
    ...item,
    id: briefing.id,
    title: briefing.title,
    audioUrl: briefing.audio_url || '',
    transcript: briefing.transcript,
    chapters: briefing.chapters,
    breakout: {
      ...item.breakout!,
      status: failed ? 'failed' : briefing.status === 'completed' ? 'ready'
        : briefing.status === 'generating' ? 'generating' : 'queued',
      error: failed ? briefing.error_message || 'Deep dive unavailable. Please try again.' : undefined,
    },
  }
}

/** Capture the audible topic synchronously, before any request or later seek. */
export async function startPlayerBreakout(source: Briefing, playbackTime: number): Promise<void> {
  const state = useStore.getState()
  const profileId = state.currentProfile?.id
  const chapterIndex = findActiveChapterIndex(source.chapters, playbackTime)
  if (!profileId || source.id !== state.currentAudio?.id || source.status !== 'completed' || chapterIndex == null) {
    throw new Error('A current chapter is needed to create a deep dive.')
  }
  if (state.queue.some(item => item.breakout?.profileId === profileId &&
    item.breakout.sourceBriefingId === source.id && item.breakout.chapterIndex === chapterIndex &&
    item.breakout.status !== 'failed')) return

  const item: QueueItem = {
    id: `breakout-request:${Date.now()}:${++requestSequence}`,
    type: 'briefing',
    title: `Deep dive: ${source.chapters![chapterIndex].title}`,
    audioUrl: '',
    breakout: { profileId, sourceBriefingId: source.id, chapterIndex, status: 'requesting' },
  }
  state.playNext(item)
  try {
    const briefing = await briefingsApi.generateBreakout({
      source_briefing_id: source.id,
      chapter_index: chapterIndex,
      max_duration_minutes: 10,
    }, profileId)
    useStore.getState().updateQueueItem(item.id, applyBriefing(item, briefing))
  } catch (error) {
    useStore.getState().updateQueueItem(item.id, {
      ...item, breakout: { ...item.breakout!, status: 'failed', error: breakoutError(error) },
    })
    throw error
  }
}

/** Poll persisted reservations, updating their existing slots without re-adding removed items. */
export async function refreshQueuedBreakouts(): Promise<void> {
  const { queue, currentProfile } = useStore.getState()
  const pending = queue.filter(item => (item.breakout?.status === 'queued' || item.breakout?.status === 'generating') &&
    item.breakout.profileId === currentProfile?.id)
  await Promise.all(pending.map(async item => {
    if (polling.has(item.id)) return
    polling.add(item.id)
    try {
      const briefing = await briefingsApi.get(item.id, item.breakout!.profileId)
      useStore.getState().updateQueueItem(item.id, applyBriefing(item, briefing))
    } catch (error) {
      if (axios.isAxiosError(error) && [403, 404].includes(error.response?.status || 0)) {
        useStore.getState().updateQueueItem(item.id, {
          ...item, breakout: { ...item.breakout!, status: 'failed', error: 'Deep dive is no longer available.' },
        })
      }
      // Temporary connectivity failures retain the reservation for the next poll.
    } finally {
      polling.delete(item.id)
    }
  }))
}
