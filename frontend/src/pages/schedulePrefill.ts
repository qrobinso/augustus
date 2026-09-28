// Query-string contract for prefilling the Create Schedule page.
// Params: topicIds (comma-separated), castId, durationMinutes, name.

const MIN_DURATION = 1
const MAX_DURATION = 60

export interface SchedulePrefill {
  topicIds: string[]
  castId?: string
  durationMinutes?: number
  name?: string
}

interface BriefingLike {
  title?: string
  duration_seconds?: number
  cast_id?: string
  extra_data?: { topic_ids?: unknown } | null
}

function clampDuration(minutes: number): number {
  return Math.min(MAX_DURATION, Math.max(MIN_DURATION, minutes))
}

/** Build the Create Schedule query params that recreate a briefing on a schedule. */
export function scheduleParamsFromBriefing(briefing: BriefingLike): URLSearchParams {
  const params = new URLSearchParams()
  const rawTopicIds = briefing.extra_data?.topic_ids
  const topicIds = Array.isArray(rawTopicIds)
    ? rawTopicIds.filter((t): t is string => typeof t === 'string' && t.length > 0)
    : []

  if (topicIds.length > 0) {
    params.set('topicIds', topicIds.join(','))
  } else if (briefing.title?.trim()) {
    // Without topics the form would auto-name it "All Topics Briefing";
    // keep the briefing's own title instead.
    params.set('name', briefing.title.trim())
  }
  if (briefing.cast_id) {
    params.set('castId', briefing.cast_id)
  }
  if (briefing.duration_seconds && briefing.duration_seconds > 0) {
    params.set('durationMinutes', String(clampDuration(Math.ceil(briefing.duration_seconds / 60))))
  }
  return params
}

/** Read Create Schedule prefill values from the URL. */
export function parseSchedulePrefill(searchParams: URLSearchParams): SchedulePrefill {
  const topicIds = (searchParams.get('topicIds') || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
  const castId = searchParams.get('castId') || undefined
  const name = searchParams.get('name')?.trim() || undefined
  const rawDuration = Number.parseInt(searchParams.get('durationMinutes') || '', 10)
  const durationMinutes = Number.isFinite(rawDuration) && rawDuration > 0
    ? clampDuration(rawDuration)
    : undefined
  return { topicIds, castId, durationMinutes, name }
}
