import type { BreakoutGenerateRequest, Briefing, Chapter } from '../api/client'

export type BreakoutTarget = 'saved-topic' | 'subject' | 'chapter'

export interface BreakoutFormValues {
  target: BreakoutTarget
  topicId?: string
  topic?: string
  sourceBriefingId?: string
  chapterIndex?: number | null
  focus?: string
  durationMinutes: 5 | 10 | 20
  castId?: string
}

export interface BreakoutSource {
  id: string
  title: string
  castId?: string
  chapters: Chapter[]
  initialChapterIndex: number | null
}

export function getBreakoutCastDefaultLabel(
  target: BreakoutTarget,
  sourceCastId?: string
): 'Same cast as source' | 'Default cast' {
  return target === 'chapter' && sourceCastId ? 'Same cast as source' : 'Default cast'
}

export function captureBreakoutSource(
  briefing: Briefing | undefined,
  initialChapterIndex: number | null | undefined
): BreakoutSource | null {
  if (!briefing) return null
  const chapters = (briefing.chapters || []).map((chapter) => ({ ...chapter }))
  const initialIndex = initialChapterIndex != null && initialChapterIndex >= 0 && initialChapterIndex < chapters.length
    ? initialChapterIndex
    : chapters.length > 0 ? 0 : null
  return {
    id: briefing.id,
    title: briefing.title,
    castId: briefing.cast_id,
    chapters,
    initialChapterIndex: initialIndex,
  }
}

export function buildBreakoutRequest(values: BreakoutFormValues): BreakoutGenerateRequest {
  let target: Pick<BreakoutGenerateRequest, 'topic' | 'topic_id' | 'source_briefing_id' | 'chapter_index'>

  if (values.target === 'saved-topic') {
    if (!values.topicId) throw new Error('Choose a saved topic')
    target = { topic_id: values.topicId }
  } else if (values.target === 'subject') {
    const topic = values.topic?.trim()
    if (!topic) throw new Error('Enter a subject')
    target = { topic }
  } else {
    if (!values.sourceBriefingId || values.chapterIndex == null) {
      throw new Error('Choose a chapter')
    }
    target = {
      source_briefing_id: values.sourceBriefingId,
      chapter_index: values.chapterIndex,
    }
  }

  const focus = values.focus?.trim()
  return {
    ...target,
    ...(focus ? { focus } : {}),
    max_duration_minutes: values.durationMinutes,
    ...(values.castId ? { cast_id: values.castId } : {}),
  }
}

export function findActiveChapterIndex(chapters: Chapter[] | undefined, currentTime: number): number | null {
  if (!chapters || !Number.isFinite(currentTime) || currentTime < 0) return null
  const index = chapters.findIndex((chapter, index) =>
    currentTime >= chapter.start_time &&
    currentTime < (chapter.end_time ?? chapters[index + 1]?.start_time ?? Infinity)
  )
  return index >= 0 ? index : null
}

export function findAutoPlayableCompletion(
  briefings: Briefing[],
  previousInProgressIds: ReadonlySet<string>,
  playback?: { currentAudio: { id: string } | null; queue: ReadonlyArray<{ id: string }> }
): Briefing | null {
  if (playback?.currentAudio || playback?.queue.length) return null
  return briefings.find((briefing) =>
    briefing.status === 'completed' &&
    previousInProgressIds.has(briefing.id) &&
    !!briefing.audio_url &&
    briefing.extra_data?.kind !== 'breakout'
  ) || null
}
