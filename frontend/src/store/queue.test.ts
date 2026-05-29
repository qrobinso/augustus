import { describe, it, expect } from 'vitest'
import { addToQueue, playNext, removeFromQueue, reorderQueue, type QueueItem } from './queue'

const item = (id: string): QueueItem => ({ id, type: 'briefing', title: id, audioUrl: `/audio/${id}.mp3` })

describe('queue logic', () => {
  it('appends to queue, no duplicates', () => {
    let q: QueueItem[] = []
    q = addToQueue(q, item('a'))
    q = addToQueue(q, item('b'))
    q = addToQueue(q, item('a'))
    expect(q.map(i => i.id)).toEqual(['a', 'b'])
  })

  it('playNext inserts at head and dedupes existing', () => {
    let q: QueueItem[] = [item('a'), item('b')]
    q = playNext(q, item('b'))
    expect(q.map(i => i.id)).toEqual(['b', 'a'])
    q = playNext(q, item('c'))
    expect(q.map(i => i.id)).toEqual(['c', 'b', 'a'])
  })

  it('removeFromQueue removes by id', () => {
    const q = removeFromQueue([item('a'), item('b'), item('c')], 'b')
    expect(q.map(i => i.id)).toEqual(['a', 'c'])
  })

  it('reorderQueue moves item between indices', () => {
    const q = reorderQueue([item('a'), item('b'), item('c')], 0, 2)
    expect(q.map(i => i.id)).toEqual(['b', 'c', 'a'])
  })

  it('reorderQueue is a no-op for out-of-range indices', () => {
    const orig = [item('a'), item('b')]
    expect(reorderQueue(orig, 5, 0).map(i => i.id)).toEqual(['a', 'b'])
  })
})
