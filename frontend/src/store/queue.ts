export interface QueueItem {
  id: string
  type: 'briefing'
  title: string
  audioUrl: string
  transcript?: string
  chapters?: Array<{ title: string; start_time: number; end_time?: number }>
}

/** Append item to the end, ignoring if its id is already queued. */
export function addToQueue(queue: QueueItem[], item: QueueItem): QueueItem[] {
  if (queue.some(q => q.id === item.id)) return queue
  return [...queue, item]
}

/** Put item at the head; remove any existing copy first. */
export function playNext(queue: QueueItem[], item: QueueItem): QueueItem[] {
  return [item, ...queue.filter(q => q.id !== item.id)]
}

export function removeFromQueue(queue: QueueItem[], id: string): QueueItem[] {
  return queue.filter(q => q.id !== id)
}

export function reorderQueue(queue: QueueItem[], from: number, to: number): QueueItem[] {
  if (from < 0 || from >= queue.length || to < 0 || to >= queue.length || from === to) {
    return queue
  }
  const next = [...queue]
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}
