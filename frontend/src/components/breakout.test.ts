import { describe, expect, it } from 'vitest'
import {
  buildBreakoutRequest,
  captureBreakoutSource,
  findActiveChapterIndex,
  findAutoPlayableCompletion,
  getBreakoutCastDefaultLabel,
} from './breakout'
import type { Briefing } from '../api/client'

describe('buildBreakoutRequest', () => {
  it('sends exactly the selected saved-topic target and omits empty optional fields', () => {
    expect(buildBreakoutRequest({
      target: 'saved-topic',
      topicId: 'topic-1',
      topic: 'ignored typed subject',
      focus: '   ',
      durationMinutes: 10,
      castId: '',
    })).toEqual({
      topic_id: 'topic-1',
      max_duration_minutes: 10,
    })
  })

  it('trims a typed subject and focus before submission', () => {
    expect(buildBreakoutRequest({
      target: 'subject',
      topic: '  orbital data centers  ',
      focus: '  focus on cooling constraints  ',
      durationMinutes: 20,
      castId: 'cast-2',
    })).toEqual({
      topic: 'orbital data centers',
      focus: 'focus on cooling constraints',
      max_duration_minutes: 20,
      cast_id: 'cast-2',
    })
  })

  it('keeps the chapter index paired with its source briefing', () => {
    expect(buildBreakoutRequest({
      target: 'chapter',
      sourceBriefingId: 'briefing-7',
      chapterIndex: 2,
      durationMinutes: 5,
    })).toEqual({
      source_briefing_id: 'briefing-7',
      chapter_index: 2,
      max_duration_minutes: 5,
    })
  })

  it('rejects an incomplete target instead of sending an ambiguous request', () => {
    expect(() => buildBreakoutRequest({
      target: 'chapter',
      sourceBriefingId: 'briefing-7',
      chapterIndex: null,
      durationMinutes: 10,
    })).toThrow('Choose a chapter')
  })
})

describe('findActiveChapterIndex', () => {
  const chapters = [
    { title: 'Introduction', start_time: 0, end_time: 12 },
    { title: 'First story', start_time: 12, end_time: 40 },
    { title: 'Second story', start_time: 40 },
  ]

  it('preselects the chapter containing the current playback time', () => {
    expect(findActiveChapterIndex(chapters, 28)).toBe(1)
    expect(findActiveChapterIndex(chapters, 40)).toBe(2)
  })

  it('returns null when the playback position does not match a chapter', () => {
    expect(findActiveChapterIndex([], 10)).toBeNull()
    expect(findActiveChapterIndex(chapters, -1)).toBeNull()
  })
})

describe('captureBreakoutSource', () => {
  it('keeps the opening source and chapter stable if the playing briefing changes', () => {
    const source = completedBriefing('source-1')
    source.title = 'Original episode'
    source.cast_id = 'cast-1'
    source.chapters = [{ title: 'Original chapter', start_time: 10 }]

    const snapshot = captureBreakoutSource(source, 0)
    source.id = 'source-2'
    source.chapters[0].title = 'Replacement chapter'

    expect(snapshot).toEqual({
      id: 'source-1',
      title: 'Original episode',
      castId: 'cast-1',
      chapters: [{ title: 'Original chapter', start_time: 10 }],
      initialChapterIndex: 0,
    })
  })
})

describe('getBreakoutCastDefaultLabel', () => {
  it('offers source cast inheritance only for a source chapter target', () => {
    expect(getBreakoutCastDefaultLabel('chapter', 'cast-1')).toBe('Same cast as source')
    expect(getBreakoutCastDefaultLabel('saved-topic', 'cast-1')).toBe('Default cast')
    expect(getBreakoutCastDefaultLabel('subject', 'cast-1')).toBe('Default cast')
  })
})

function completedBriefing(id: string, kind?: string): Briefing {
  return {
    id,
    user_id: 'user-1',
    title: id,
    audio_url: `/audio/${id}.mp3`,
    extra_data: kind ? { kind } : {},
    sources: [],
    status: 'completed',
    created_at: '2026-09-04T12:00:00Z',
    listened: false,
    favorite: false,
  }
}

describe('findAutoPlayableCompletion', () => {
  it('never selects a completed breakout for automatic playback', () => {
    expect(findAutoPlayableCompletion(
      [completedBriefing('breakout-1', 'breakout')],
      new Set(['breakout-1'])
    )).toBeNull()
  })

  it('still selects a regular briefing that just completed', () => {
    expect(findAutoPlayableCompletion(
      [completedBriefing('daily-1')],
      new Set(['daily-1'])
    )?.id).toBe('daily-1')
  })
})
