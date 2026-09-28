import { useState, useEffect, useRef } from 'react'
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Loader2,
  Sparkles,
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle,
  Check,
  Search,
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, topicsApi, castsApi, customSitesApi, settingsApi, Briefing } from '../api/client'
import { useStore } from '../store/useStore'
import { useProfileNavigate } from '../utils/profileSlug'
import { findAutoPlayableCompletion } from '../components/breakout'

const PRESET_COLORS = [
  '#3B82F6', // Blue
  '#10B981', // Green
  '#8B5CF6', // Purple
  '#EF4444', // Red
  '#F97316', // Orange
  '#EC4899', // Pink
  '#06B6D4', // Cyan
  '#F59E0B', // Amber
  '#6366F1', // Indigo
  '#84CC16', // Lime
]

export function trackAcceptedBriefing(
  previous: { profileId?: string; ids: string[] },
  id: string,
  requestProfileId: string,
  currentProfileId: string | undefined,
) {
  if (requestProfileId !== currentProfileId) return previous
  const ids = previous.profileId === requestProfileId ? previous.ids : []
  return { profileId: requestProfileId, ids: [...new Set([...ids, id])] }
}

const DURATION_PRESETS = [5, 10, 15, 20, 30]

/** Length choices offered in the form, always including the configured default. */
export function durationChoices(defaultMinutes?: number): number[] {
  if (!defaultMinutes || DURATION_PRESETS.includes(defaultMinutes)) return DURATION_PRESETS
  return [...DURATION_PRESETS, defaultMinutes].sort((a, b) => a - b)
}

const TOPIC_FILTER_THRESHOLD = 12

/** Topics matching the filter text; selected topics always stay visible so they can be unselected. */
export function filterTopics<T extends { id: string; name: string }>(topics: T[], query: string, selectedIds: string[]): T[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return topics
  return topics.filter(topic => selectedIds.includes(topic.id) || topic.name.toLowerCase().includes(needle))
}

export type TopicMode = 'existing' | 'new'

/** One-line recap shown next to the create button. */
export function briefingSummary(options: {
  mode: TopicMode
  selectedTopicNames: string[]
  durationMinutes?: number
  castName?: string
}): string {
  const about = options.mode === 'new'
    ? 'New topic'
    : options.selectedTopicNames.length === 0
      ? 'All topics'
      : options.selectedTopicNames.length <= 2
        ? options.selectedTopicNames.join(' & ')
        : `${options.selectedTopicNames.length} topics`
  return [
    options.durationMinutes ? `${options.durationMinutes} min` : null,
    about,
    options.castName || null,
  ].filter(Boolean).join(' · ')
}

interface DashboardGenerateProps {
  /** Called once generation has been kicked off (used by the sheet to dismiss itself). */
  onGenerateStarted?: () => void
  /** Called when the form navigates elsewhere (used by the sheet to close itself). */
  onNavigateAway?: () => void
}

export default function DashboardGenerate({ onGenerateStarted, onNavigateAway }: DashboardGenerateProps) {
  const navigate = useProfileNavigate()
  const queryClient = useQueryClient()
  const profileId = useStore((s) => s.currentProfile?.id)
  const playAudio = useStore((s) => s.playAudio)
  
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([])
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(() => {
    const saved = localStorage.getItem('selectedCastId')
    return saved || undefined
  })
  
  const [topicMode, setTopicMode] = useState<TopicMode>('existing')
  const [durationMinutes, setDurationMinutes] = useState<number | undefined>(undefined)
  const [topicFilter, setTopicFilter] = useState('')

  // Prompt-based topic generation state
  const [topicPrompt, setTopicPrompt] = useState('')
  const [promptError, setPromptError] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  
  const [tracked, setTracked] = useState<{ profileId?: string; ids: string[] }>({ profileId, ids: [] })
  const [ready, setReady] = useState<{ profileId?: string; briefings: Briefing[] }>({ profileId, briefings: [] })
  const handledCompletions = useRef(new Set<string>())
  const { data: queueData, isError: queueError } = useQuery({
    queryKey: ['briefings', 'queue', profileId],
    queryFn: () => briefingsApi.queue(profileId!),
    enabled: !!profileId,
    refetchInterval: (query) => query.state.data?.briefings.length ? 2000 : 10000,
  })
  const activeBriefings = queueData?.briefings || []
  const trackedIds = tracked.profileId === profileId ? tracked.ids : []
  useEffect(() => {
    const ids = queueData?.briefings.map(briefing => briefing.id) || []
    setTracked(previous => {
      const previousIds = previous.profileId === profileId ? previous.ids : []
      const added = ids.filter(id => !previousIds.includes(id))
      return previous.profileId === profileId && !added.length ? previous
        : { profileId, ids: [...previousIds, ...added] }
    })
  }, [queueData, profileId])

  // Follow jobs that leave the active queue by ID, even when history is paginated.
  const finishedQueries = useQueries({
    queries: trackedIds.filter(id => !activeBriefings.some(briefing => briefing.id === id)).map(id => ({
      queryKey: ['briefing', id, profileId],
      queryFn: () => briefingsApi.get(id, profileId),
      refetchInterval: (query: { state: { data?: Briefing } }) => {
        const status = query.state.data?.status
        return status === 'pending' || status === 'queued' || status === 'generating' ? 2000 : false as const
      },
    })),
  })
  useEffect(() => {
    const completed = finishedQueries.map(query => query.data).filter((briefing): briefing is Briefing =>
      !!briefing && ['completed', 'failed', 'cancelled'].includes(briefing.status) &&
      !handledCompletions.current.has(briefing.id))
    if (!completed.length) return
    completed.forEach(briefing => handledCompletions.current.add(briefing.id))
    const playable = completed.filter(briefing => briefing.status === 'completed' && !!briefing.audio_url)
    if (playable.length) {
      setReady(previous => ({ profileId, briefings: [
        ...(previous.profileId === profileId ? previous.briefings : []), ...playable,
      ] }))
    }
    const autoPlayable = findAutoPlayableCompletion(completed, new Set(trackedIds), useStore.getState())
    if (autoPlayable && useStore.getState().currentProfile?.id === profileId) {
      playAudio({ id: autoPlayable.id, type: 'briefing', title: autoPlayable.title,
        audioUrl: autoPlayable.audio_url!, transcript: autoPlayable.transcript, chapters: autoPlayable.chapters })
      navigate(`/briefing/${autoPlayable.id}`)
    }
    setTracked(previous => ({ ...previous, ids: previous.ids.filter(id => !completed.some(briefing => briefing.id === id)) }))
    queryClient.invalidateQueries({ queryKey: ['briefings'] })
  }, [finishedQueries, trackedIds, profileId, playAudio, navigate, queryClient])

  // Fetch topics
  const { data: topicsData, isLoading: topicsLoading } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  // Fetch casts
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })

  const topics = topicsData?.topics || []
  const casts = castsData?.casts || []
  const defaultCast = casts.find(c => c.is_default)
  const defaultDuration = settings?.briefing_duration_minutes
  const selectedDuration = durationMinutes ?? defaultDuration
  
  // Handle starting playback and navigating
  const handlePlayAndNavigate = (briefing: Briefing) => {
    if (!briefing.audio_url) return
    
    playAudio({
      id: briefing.id,
      type: 'briefing',
      title: briefing.title,
      audioUrl: briefing.audio_url,
      transcript: briefing.transcript,
      chapters: briefing.chapters,
      initialPosition: briefing.playback_position || undefined,
    })
    
    navigate(`/briefing/${briefing.id}`)
  }
  
  const generateMutation = useMutation({
    mutationFn: (options: { topicIds?: string[]; castId?: string; durationMinutes?: number; profileId: string }) => briefingsApi.generate({
      topic_ids: options?.topicIds && options.topicIds.length > 0 ? options.topicIds : undefined,
      cast_id: options.castId,
      max_duration_minutes: options.durationMinutes,
    }, options.profileId),
    onSuccess: (briefing, options) => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
      setIsGenerating(false)
      if (useStore.getState().currentProfile?.id !== options.profileId) return
      setTracked(previous => trackAcceptedBriefing(
        previous, briefing.id, options.profileId, useStore.getState().currentProfile?.id,
      ))
      onGenerateStarted?.()
    },
    onError: (error: Error, options) => {
      setIsGenerating(false)
      if (useStore.getState().currentProfile?.id !== options.profileId) return
      setPromptError(error.message || 'Could not queue this briefing. Try again.')
    },
  })

  const [cancellingIds, setCancellingIds] = useState<Set<string>>(new Set())
  const cancelMutation = useMutation({
    mutationFn: (request: { id: string; profileId: string }) => briefingsApi.cancel(request.id, request.profileId),
    onMutate: ({ id }) => {
      setPromptError(null)
      setCancellingIds(previous => new Set(previous).add(id))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
    onError: (error: Error, request) => {
      if (useStore.getState().currentProfile?.id === request.profileId) {
        setPromptError(error.message || 'Could not cancel this briefing. Try again.')
      }
    },
    onSettled: (_data, _error, { id }) => setCancellingIds(previous => {
      const next = new Set(previous)
      next.delete(id)
      return next
    }),
  })

  // Persist selectedCastId to localStorage
  useEffect(() => {
    if (selectedCastId) {
      localStorage.setItem('selectedCastId', selectedCastId)
    }
  }, [selectedCastId])
  
  // Initialize selectedCastId with default cast
  useEffect(() => {
    if (defaultCast && selectedCastId === undefined) {
      setSelectedCastId(defaultCast.id)
    }
  }, [defaultCast, selectedCastId])
  
  // Validate selectedCastId exists
  useEffect(() => {
    if (casts.length > 0 && selectedCastId) {
      const castExists = casts.some(c => c.id === selectedCastId)
      if (!castExists) {
        localStorage.removeItem('selectedCastId')
        setSelectedCastId(defaultCast?.id)
      }
    }
  }, [casts, selectedCastId, defaultCast?.id])
  
  const toggleTopic = (topicId: string) => {
    setSelectedTopicIds((prev) =>
      prev.includes(topicId)
        ? prev.filter((id) => id !== topicId)
        : [...prev, topicId]
    )
  }
  
  // Normalize URL for duplicate checking
  const normalizeUrl = (url: string): string => {
    return url.trim().toLowerCase().replace(/\/$/, '')
  }
  
  // Normalize topic name for comparison (lowercase, trim, remove extra spaces)
  const normalizeTopicName = (name: string): string => {
    return name.trim().toLowerCase().replace(/\s+/g, ' ')
  }
  
  // Check if a topic with similar name already exists
  const findExistingTopic = (topicName: string): string | null => {
    const normalizedName = normalizeTopicName(topicName)
    const existingTopic = topics.find(t => normalizeTopicName(t.name) === normalizedName)
    return existingTopic?.id || null
  }
  
  const [stage, setStage] = useState<string | null>(null)
  const busy = isGenerating || generateMutation.isPending
  const canSubmit = !busy && !!profileId && (topicMode === 'existing' || !!topicPrompt.trim())

  const handleGenerate = async () => {
    const requestProfileId = profileId
    if (!requestProfileId || !canSubmit) return
    setIsGenerating(true)
    setPromptError(null)
    
    try {
      let topicIds = selectedTopicIds
      if (topicMode === 'new') {
        // Turn the prompt into a saved topic (reusing a same-named one) with suggested sites
        setStage('Drafting topic…')
        const generatedTopic = await topicsApi.generateFromPrompt(topicPrompt.trim())
        
        const existingTopicId = findExistingTopic(generatedTopic.name)
        let topicToUse
        
        if (existingTopicId) {
          topicToUse = topics.find(t => t.id === existingTopicId)!
        } else {
          const topicColor = PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)]
          topicToUse = await topicsApi.create({
            name: generatedTopic.name,
            description: generatedTopic.description,
            color: topicColor,
            use_newsapi: generatedTopic.use_newsapi,
          })
        }
        
        setStage('Adding sources…')
        const existingSitesData = await customSitesApi.list()
        const existingUrls = new Set(
          existingSitesData.sites.map(site => normalizeUrl(site.url))
        )
        
        const seenUrls = new Set<string>()
        const sitesToCreate: Array<{ name: string; url: string }> = []
        
        for (const site of generatedTopic.sites) {
          const normalizedUrl = normalizeUrl(site.url)
          
          // Skip if already seen in this batch or exists in database
          if (seenUrls.has(normalizedUrl) || existingUrls.has(normalizedUrl)) {
            continue
          }
          
          seenUrls.add(normalizedUrl)
          sitesToCreate.push(site)
        }
        
        // Create sites, continuing even if some fail
        for (const site of sitesToCreate) {
          try {
            await customSitesApi.create({
              name: site.name,
              url: site.url,
              topic_id: topicToUse.id,
            })
          } catch (err: unknown) {
            // Silently continue - site creation failures shouldn't block briefing generation
            console.error(`Failed to create site ${site.name}:`, err)
          }
        }
        
        queryClient.invalidateQueries({ queryKey: ['topics'] })
        queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
        
        topicIds = [topicToUse.id]
        setTopicPrompt('')
        setTopicMode('existing')
        setSelectedTopicIds([topicToUse.id])
      }

      setStage('Starting…')
      generateMutation.mutate({
        profileId: requestProfileId,
        topicIds: topicIds.length > 0 ? topicIds : undefined,
        castId: selectedCastId,
        durationMinutes: selectedDuration,
      })
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create topic from prompt'
      setPromptError(errorMessage)
      setIsGenerating(false)
    }
  }

  const goToTopics = () => {
    onNavigateAway?.()
    navigate('/topics')
  }

  const showTopicFilter = topics.length > TOPIC_FILTER_THRESHOLD
  const visibleTopics = showTopicFilter ? filterTopics(topics, topicFilter, selectedTopicIds) : topics

  const selectedCast = casts.find(c => c.id === selectedCastId)
  const summary = briefingSummary({
    mode: topicMode,
    selectedTopicNames: topics.filter(t => selectedTopicIds.includes(t.id)).map(t => t.name),
    durationMinutes: selectedDuration,
    castName: casts.length > 1 ? selectedCast?.name : undefined,
  })

  const chipClass = (active: boolean) => clsx(
    'px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5 min-h-[36px]',
    active
      ? 'bg-accent text-white'
      : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
  )
  
  return (
    <div>
      {/* What it's about */}
      <section className="mb-6" aria-labelledby="briefing-about">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h3 id="briefing-about" className="text-sm font-medium text-white">What's it about?</h3>
          <div className="inline-flex bg-augustus-800/60 p-1 rounded-full" role="radiogroup" aria-label="Topic source">
            {([['existing', 'My topics'], ['new', 'Something new']] as const).map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                role="radio"
                aria-checked={topicMode === mode}
                onClick={() => { setTopicMode(mode); setPromptError(null) }}
                disabled={busy}
                className={clsx(
                  'px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all',
                  topicMode === mode ? 'bg-accent text-white' : 'text-augustus-300 hover:text-white'
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {topicMode === 'new' ? (
          <div>
            <label htmlFor="briefing-prompt" className="sr-only">Describe what you want to hear about</label>
            <textarea
              id="briefing-prompt"
              value={topicPrompt}
              onChange={(e) => setTopicPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault()
                  handleGenerate()
                }
              }}
              placeholder="e.g. The latest in electric vehicles and sustainable transportation"
              className="input min-h-[96px] resize-none"
              disabled={busy}
              autoFocus
            />
            <p className="text-xs text-augustus-500 mt-2">
              Saves this as a new topic with suggested sources, so you can reuse it or edit it later in Topics.
            </p>
          </div>
        ) : topicsLoading ? (
          <div className="flex items-center gap-2 text-augustus-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Loading topics...</span>
          </div>
        ) : (
          <div>
            {showTopicFilter && (
              <div className="relative mb-3">
                <Search className="w-4 h-4 text-augustus-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="search"
                  value={topicFilter}
                  onChange={(e) => setTopicFilter(e.target.value)}
                  placeholder={`Filter ${topics.length} topics`}
                  aria-label="Filter topics"
                  className="input pl-9 py-2 text-sm"
                  disabled={busy}
                />
              </div>
            )}
            <div className={clsx('flex flex-wrap gap-2', showTopicFilter && 'max-h-52 sm:max-h-64 overflow-y-auto overscroll-contain pr-1')}>
              <button
                type="button"
                aria-pressed={selectedTopicIds.length === 0}
                onClick={() => setSelectedTopicIds([])}
                disabled={busy}
                className={chipClass(selectedTopicIds.length === 0)}
              >
                {selectedTopicIds.length === 0 && <Check className="w-3.5 h-3.5" />}
                All topics
              </button>
              {visibleTopics.map((topic) => {
                const selected = selectedTopicIds.includes(topic.id)
                return (
                  <button
                    key={topic.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => toggleTopic(topic.id)}
                    disabled={busy}
                    className={clsx(
                      'px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5 min-h-[36px]',
                      selected
                        ? 'text-white'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                    )}
                    style={selected ? { backgroundColor: topic.color || '#3B82F6' } : undefined}
                  >
                    {selected
                      ? <Check className="w-3.5 h-3.5" />
                      : <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: topic.color || '#3B82F6' }} />}
                    {topic.name}
                  </button>
                )
              })}
            </div>
            {showTopicFilter && topicFilter.trim() && visibleTopics.length === selectedTopicIds.length && (
              <p className="text-sm text-augustus-500 mt-3">No other topics match "{topicFilter.trim()}".</p>
            )}
            {topics.length === 0 && (
              <p className="text-sm text-augustus-500 mt-3">
                You haven't created any topics yet, so this covers your general news sources.{' '}
                <button type="button" onClick={goToTopics} className="text-accent hover:underline">Set up topics</button>
                {' '}or try <button type="button" onClick={() => setTopicMode('new')} className="text-accent hover:underline">Something new</button>.
              </p>
            )}
          </div>
        )}
      </section>

      {/* Length */}
      <section className="mb-6" aria-labelledby="briefing-length">
        <h3 id="briefing-length" className="text-sm font-medium text-white mb-3">Length</h3>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-labelledby="briefing-length">
          {durationChoices(defaultDuration).map(minutes => (
            <button
              key={minutes}
              type="button"
              role="radio"
              aria-checked={selectedDuration === minutes}
              onClick={() => setDurationMinutes(minutes)}
              disabled={busy}
              className={chipClass(selectedDuration === minutes)}
            >
              {minutes} min
              {minutes === defaultDuration && (
                <span className={clsx('text-xs', selectedDuration === minutes ? 'text-white/70' : 'text-augustus-500')}>· default</span>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* Hosts */}
      {casts.length > 1 && (
        <section className="mb-6">
          <label htmlFor="briefing-cast" className="block text-sm font-medium text-white mb-3">Hosts</label>
          <select
            id="briefing-cast"
            value={selectedCastId || ''}
            onChange={(e) => setSelectedCastId(e.target.value || undefined)}
            disabled={busy}
            className="input w-full"
          >
            {casts.map((cast) => (
              <option key={cast.id} value={cast.id}>
                {cast.name}{cast.is_default ? ' (default)' : ''}
              </option>
            ))}
          </select>
        </section>
      )}

      {ready.profileId === profileId && ready.briefings.map(briefing => (
        <div key={briefing.id} className="mb-4 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-green-400 font-medium">Briefing ready!</p>
              <p className="text-sm text-augustus-400 mb-3 truncate">{briefing.title}</p>
              <button onClick={() => handlePlayAndNavigate(briefing)} className="btn btn-primary flex items-center gap-2">
                <Play className="w-4 h-4" /> Play & View Details
              </button>
            </div>
          </div>
        </div>
      ))}

      {queueError && <p role="alert" className="text-sm text-red-400 mb-4">Could not load the generation queue. Retrying automatically.</p>}
      {activeBriefings.length > 0 && (
        <section className="mb-6 space-y-2" aria-label="Generation queue">
          <h3 className="text-sm font-medium text-white">
            In progress <span className="text-augustus-500 font-normal">· {activeBriefings.length}</span>
          </h3>
          {activeBriefings.map(briefing => {
            const generating = briefing.status === 'generating'
            const progress = briefing.extra_data?.progress
            const cancelling = cancellingIds.has(briefing.id)
            return (
              <div key={briefing.id} className="p-3 rounded-lg bg-augustus-800/50 border border-augustus-700/50">
                <div className="flex items-center gap-3">
                  {generating ? <Loader2 className="w-4 h-4 animate-spin text-accent flex-shrink-0" />
                    : <Clock className="w-4 h-4 text-augustus-400 flex-shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-augustus-100 truncate">{briefing.title}</p>
                    <p className="text-xs text-augustus-500">
                      {generating
                        ? `Generating briefing${progress ? ` · ${progress.step_name} · ${progress.percent}%` : '…'}`
                        : 'Queued for generation · starts automatically'}
                    </p>
                    {generating && progress && (
                      <div className="mt-2 h-1 bg-augustus-800 rounded-full overflow-hidden">
                        <div className="h-full bg-accent rounded-full transition-all duration-500" style={{ width: `${progress.percent}%` }} />
                      </div>
                    )}
                  </div>
                  <button onClick={() => profileId && cancelMutation.mutate({ id: briefing.id, profileId })} disabled={cancelling}
                    className="btn btn-ghost p-2 text-augustus-400 hover:text-red-400 hover:bg-red-500/10 flex-shrink-0"
                    aria-label={`Cancel ${briefing.title}`} title="Cancel briefing">
                    {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )
          })}
        </section>
      )}

      {/* Action bar stays in reach while the sheet scrolls */}
      <div className="sticky bottom-0 -mx-4 sm:-mx-6 px-4 sm:px-6 pt-3 pb-1 bg-augustus-900/95 backdrop-blur-sm border-t border-augustus-800">
        {promptError && (
          <div role="alert" className="flex items-start gap-2 text-red-400 text-sm mb-3">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{promptError}</span>
          </div>
        )}
        <div className="flex flex-col-reverse sm:flex-row sm:items-center gap-2 sm:gap-4">
          <p className="text-xs text-augustus-400 flex-1 min-w-0 truncate text-center sm:text-left">{summary}</p>
          <button
            onClick={handleGenerate}
            disabled={!canSubmit}
            className="btn btn-primary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto"
          >
            {busy ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {stage || 'Starting…'}
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                {activeBriefings.length ? 'Queue another briefing' : 'Create briefing'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
