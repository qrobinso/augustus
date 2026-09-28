// Labels for the compact filter chips on the Briefs dashboard. Each chip shows
// its active value, or its default label when that filter is unset.

type Named = { id: string; name: string }

export function statusChipLabel(listened: boolean | undefined): string {
  if (listened === true) return 'Listened'
  if (listened === false) return 'Not Listened'
  return 'Status'
}

export function castChipLabel(castId: string | undefined, casts: Named[]): string {
  if (castId === undefined) return 'All Casts'
  return casts.find((c) => c.id === castId)?.name ?? 'Cast'
}

export function topicsChipLabel(topicIds: string[], topics: Named[]): string {
  if (topicIds.length === 0) return 'All Topics'
  if (topicIds.length === 1) {
    return topics.find((t) => t.id === topicIds[0])?.name ?? '1 topic'
  }
  return `${topicIds.length} topics`
}
