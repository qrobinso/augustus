// Pure helpers for the prompt-driven "create topic" flow.

export interface DraftSite {
  name: string
  url: string
}

/** Router state carried from the Topics prompt box to the create form. */
export interface TopicPromptState {
  from?: string
  prompt?: string
}

/** Normalize a URL for duplicate checks (matches the backend's normalize_url). */
export function normalizeSiteUrl(url: string): string {
  return url.trim().toLowerCase().replace(/\/+$/, '')
}

/** Read a non-empty prompt from router state, or null. */
export function readTopicPrompt(state: unknown): string | null {
  if (!state || typeof state !== 'object') return null
  const prompt = (state as TopicPromptState).prompt
  if (typeof prompt !== 'string') return null
  const trimmed = prompt.trim()
  return trimmed ? trimmed : null
}

/** Append incoming sites to the pending list, skipping blank and duplicate URLs. */
export function mergePendingSites<T extends DraftSite>(existing: T[], incoming: T[]): T[] {
  const seen = new Set(existing.map((site) => normalizeSiteUrl(site.url)))
  const merged = [...existing]
  for (const site of incoming) {
    const key = normalizeSiteUrl(site.url)
    if (!key || seen.has(key)) continue
    seen.add(key)
    merged.push(site)
  }
  return merged
}

/** Split pending sites into ones to create and ones the user already follows. */
export function partitionNewSites<T extends DraftSite>(
  sites: T[],
  existingUrls: Iterable<string>,
): { toCreate: T[]; skipped: T[] } {
  const known = new Set(Array.from(existingUrls, normalizeSiteUrl))
  const toCreate: T[] = []
  const skipped: T[] = []
  for (const site of sites) {
    const key = normalizeSiteUrl(site.url)
    if (known.has(key)) {
      skipped.push(site)
    } else {
      known.add(key)
      toCreate.push(site)
    }
  }
  return { toCreate, skipped }
}

/** Best human-readable message from an API (axios) error. */
export function describeApiError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } } | null)?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (err instanceof Error && err.message) return err.message
  return fallback
}
