import axios from 'axios'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, Loader2, Mic2, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { briefingsApi, castsApi, topicsApi, type Briefing } from '../api/client'
import { useStore } from '../store/useStore'
import { slugify } from '../utils/profileSlug'
import {
  buildBreakoutRequest,
  captureBreakoutSource,
  getBreakoutCastDefaultLabel,
  type BreakoutSource,
  type BreakoutTarget,
} from './breakout'

interface BreakoutDialogProps {
  open: boolean
  onClose: () => void
  sourceBriefing?: Briefing
  initialChapterIndex?: number | null
}

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return error instanceof Error ? error.message : 'Could not queue the breakout podcast.'
}

export default function BreakoutDialog({
  open,
  onClose,
  sourceBriefing,
  initialChapterIndex = null,
}: BreakoutDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const subjectRef = useRef<HTMLInputElement>(null)
  const topicRef = useRef<HTMLSelectElement>(null)
  const chapterRef = useRef<HTMLSelectElement>(null)
  const wasOpenRef = useRef(false)
  const submittingRef = useRef(false)
  const currentProfile = useStore((state) => state.currentProfile)
  const queryClient = useQueryClient()
  const [scope, setScope] = useState<{ id: string; slug: string } | null>(null)
  const [source, setSource] = useState<BreakoutSource | null>(null)
  const [target, setTarget] = useState<BreakoutTarget>('subject')
  const [topicId, setTopicId] = useState('')
  const [topic, setTopic] = useState('')
  const [chapterIndex, setChapterIndex] = useState<number | null>(initialChapterIndex)
  const [focus, setFocus] = useState('')
  const [durationMinutes, setDurationMinutes] = useState<5 | 10 | 20>(10)
  const [castId, setCastId] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [queuedBriefing, setQueuedBriefing] = useState<Briefing | null>(null)

  const { data: topicsData } = useQuery({
    queryKey: ['topics', 'breakout', scope?.id],
    queryFn: () => topicsApi.list(false, scope!.id),
    enabled: open && !!scope?.id && currentProfile?.id === scope.id,
  })
  const { data: castsData } = useQuery({
    queryKey: ['casts', 'breakout', scope?.id],
    queryFn: () => castsApi.list(scope!.id),
    enabled: open && !!scope?.id && currentProfile?.id === scope.id,
  })

  const chapters = source?.chapters || []
  const profileChanged = !!scope && currentProfile?.id !== scope.id
  const detailPath = queuedBriefing && scope
    ? `/${scope.slug}/briefing/${queuedBriefing.id}`
    : ''

  const mutation = useMutation({
    mutationFn: ({ profileId }: { profileId: string }) => {
      const request = buildBreakoutRequest({
        target,
        topicId,
        topic,
        sourceBriefingId: source?.id,
        chapterIndex,
        focus,
        durationMinutes,
        castId,
      })
      return briefingsApi.generateBreakout(request, profileId)
    },
    onSuccess: (briefing) => {
      setQueuedBriefing(briefing)
      setFormError(null)
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
      queryClient.invalidateQueries({ queryKey: ['briefing', briefing.id] })
    },
    onError: (error) => setFormError(errorMessage(error)),
    onSettled: () => {
      submittingRef.current = false
    },
  })

  useEffect(() => {
    if (open && !wasOpenRef.current) {
      const profile = currentProfile
      const openingSource = captureBreakoutSource(sourceBriefing, initialChapterIndex)
      submittingRef.current = false
      setScope(profile ? { id: profile.id, slug: slugify(profile.name) } : null)
      setSource(openingSource)
      setTarget(openingSource && openingSource.chapters.length > 0 ? 'chapter' : 'subject')
      setTopicId('')
      setTopic('')
      setChapterIndex(openingSource?.initialChapterIndex ?? null)
      setFocus('')
      setDurationMinutes(10)
      setCastId('')
      setFormError(null)
      setQueuedBriefing(null)
    }
    wasOpenRef.current = open
  }, [open, currentProfile, sourceBriefing, initialChapterIndex])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      dialog.showModal()
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  useEffect(() => {
    if (!open || !dialogRef.current?.open) return
    const targetControl = target === 'subject'
      ? subjectRef.current
      : target === 'saved-topic'
        ? topicRef.current
        : chapterRef.current
    targetControl?.focus()
  }, [open, target])

  const canSubmit = useMemo(() => {
    if (!scope || profileChanged || mutation.isPending) return false
    if (target === 'subject') return !!topic.trim()
    if (target === 'saved-topic') return !!topicId
    return !!source && chapterIndex != null
  }, [scope, profileChanged, mutation.isPending, target, topic, topicId, source, chapterIndex])

  if (!open) return null

  return (
    <dialog
      ref={dialogRef}
      onCancel={(event) => {
        event.preventDefault()
        if (!mutation.isPending) onClose()
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current && !mutation.isPending) onClose()
      }}
      aria-labelledby="breakout-title"
      className="m-auto w-[calc(100%_-_2rem)] max-w-xl max-h-[90dvh] overflow-y-auto rounded-2xl border border-augustus-700/60 bg-augustus-900 p-0 text-augustus-100 shadow-2xl shadow-black/60 backdrop:bg-black/65 backdrop:backdrop-blur-sm"
    >
      <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-augustus-800 bg-augustus-900/95 px-5 py-4 backdrop-blur-sm">
        <div>
          <h2 id="breakout-title" className="font-display text-xl font-semibold text-white">
            Breakout podcast
          </h2>
          <p className="mt-1 text-sm text-augustus-400">Create a focused episode while your audio keeps playing.</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          disabled={mutation.isPending}
          className="btn btn-ghost btn-icon -mr-2 -mt-1"
          aria-label="Close breakout podcast"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {queuedBriefing ? (
        <div className="px-5 py-8 text-center">
          <CheckCircle className="mx-auto h-11 w-11 text-green-400" />
          <h3 className="mt-3 text-lg font-semibold text-white">Breakout podcast queued</h3>
          <p className="mt-2 text-sm text-augustus-400">{queuedBriefing.title}</p>
          <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
            <Link to={detailPath} onClick={onClose} className="btn btn-primary">View details</Link>
            <button type="button" onClick={onClose} className="btn btn-secondary">Keep listening</button>
          </div>
        </div>
      ) : (
        <form
          className="space-y-5 px-5 py-5"
          onSubmit={(event) => {
            event.preventDefault()
            setFormError(null)
            if (!scope || profileChanged || mutation.isPending || submittingRef.current) return
            try {
              buildBreakoutRequest({
                target,
                topicId,
                topic,
                sourceBriefingId: source?.id,
                chapterIndex,
                focus,
                durationMinutes,
                castId,
              })
              submittingRef.current = true
              mutation.mutate({ profileId: scope.id })
            } catch (error) {
              setFormError(errorMessage(error))
            }
          }}
        >
          <fieldset>
            <legend className="label">What should this episode explore?</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {source && chapters.length > 0 && (
                <button type="button" aria-pressed={target === 'chapter'} onClick={() => setTarget('chapter')} className={target === 'chapter' ? 'btn btn-primary' : 'btn btn-secondary'}>
                  Current chapter
                </button>
              )}
              <button type="button" aria-pressed={target === 'saved-topic'} onClick={() => setTarget('saved-topic')} className={target === 'saved-topic' ? 'btn btn-primary' : 'btn btn-secondary'}>
                Saved topic
              </button>
              <button type="button" aria-pressed={target === 'subject'} onClick={() => setTarget('subject')} className={target === 'subject' ? 'btn btn-primary' : 'btn btn-secondary'}>
                Type a subject
              </button>
            </div>
          </fieldset>

          {target === 'chapter' && source && (
            <div>
              <label htmlFor="breakout-chapter" className="label">Chapter from “{source.title}”</label>
              <select ref={chapterRef} id="breakout-chapter" className="input" value={chapterIndex ?? ''} onChange={(event) => setChapterIndex(Number(event.target.value))}>
                {chapters.map((chapter, index) => <option key={`${chapter.start_time}-${index}`} value={index}>{chapter.title}</option>)}
              </select>
            </div>
          )}

          {target === 'saved-topic' && (
            <div>
              <label htmlFor="breakout-topic" className="label">Saved topic</label>
              <select ref={topicRef} id="breakout-topic" className="input" value={topicId} onChange={(event) => setTopicId(event.target.value)}>
                <option value="">Choose a topic</option>
                {(topicsData?.topics || []).filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
          )}

          {target === 'subject' && (
            <div>
              <label htmlFor="breakout-subject" className="label">Subject</label>
              <input ref={subjectRef} id="breakout-subject" className="input" value={topic} onChange={(event) => setTopic(event.target.value)} maxLength={300} placeholder="e.g. Why small modular reactors are back" />
            </div>
          )}

          <div>
            <label htmlFor="breakout-focus" className="label">Focus <span className="font-normal text-augustus-500">(optional)</span></label>
            <textarea id="breakout-focus" className="input min-h-24 resize-y" value={focus} onChange={(event) => setFocus(event.target.value)} maxLength={1000} placeholder="Questions, arguments, or angles you want covered" />
            <p className="mt-1 text-right text-xs text-augustus-500">{focus.length}/1000</p>
          </div>

          <fieldset>
            <legend className="label">Length</legend>
            <div className="grid grid-cols-3 gap-2">
              {([5, 10, 20] as const).map((minutes) => (
                <button key={minutes} type="button" aria-pressed={durationMinutes === minutes} onClick={() => setDurationMinutes(minutes)} className={durationMinutes === minutes ? 'btn btn-primary' : 'btn btn-secondary'}>{minutes} min</button>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor="breakout-cast" className="label">Cast</label>
            <select id="breakout-cast" className="input" value={castId} onChange={(event) => setCastId(event.target.value)}>
              <option value="">{getBreakoutCastDefaultLabel(target, source?.castId)}</option>
              {(castsData?.casts || []).map((cast) => <option key={cast.id} value={cast.id}>{cast.name}{cast.is_default ? ' (default)' : ''}</option>)}
            </select>
          </div>

          {profileChanged && <p role="alert" className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-300">The active profile changed. Close this dialog and start the breakout again for the new profile.</p>}
          {formError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{formError}</p>}

          <button type="submit" disabled={!canSubmit} className="btn btn-primary w-full gap-2">
            {mutation.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Mic2 className="h-5 w-5" />}
            {mutation.isPending ? 'Queuing…' : 'Create breakout podcast'}
          </button>
        </form>
      )}
    </dialog>
  )
}
