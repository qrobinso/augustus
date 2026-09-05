import { useState, useEffect, useRef } from 'react'
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play,
  Loader2, 
  Sparkles, 
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, topicsApi, castsApi, customSitesApi, Briefing } from '../api/client'
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

interface DashboardGenerateProps {
  /** Called once generation has been kicked off (used by the sheet to dismiss itself). */
  onGenerateStarted?: () => void
}

export default function DashboardGenerate({ onGenerateStarted }: DashboardGenerateProps) {
  const navigate = useProfileNavigate()
  const queryClient = useQueryClient()
  const profileId = useStore((s) => s.currentProfile?.id)
  const playAudio = useStore((s) => s.playAudio)
  
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([])
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(() => {
    const saved = localStorage.getItem('selectedCastId')
    return saved || undefined
  })
  
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
  
  const topics = topicsData?.topics || []
  const casts = castsData?.casts || []
  const defaultCast = casts.find(c => c.is_default)
  
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
    mutationFn: (options: { topicIds?: string[]; castId?: string; profileId: string }) => briefingsApi.generate({
      topic_ids: options?.topicIds && options.topicIds.length > 0 ? options.topicIds : undefined,
      cast_id: options.castId,
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
  
  const handleGenerate = async () => {
    const requestProfileId = profileId
    if (!requestProfileId) return
    setIsGenerating(true)
    setPromptError(null)
    
    try {
      // If there's a prompt, generate and create the topic first
      if (topicPrompt.trim()) {
        // Generate topic from prompt
        const generatedTopic = await topicsApi.generateFromPrompt(topicPrompt.trim())
        
        // Check if a topic with the same name already exists
        const existingTopicId = findExistingTopic(generatedTopic.name)
        let topicToUse
        
        if (existingTopicId) {
          // Use existing topic
          topicToUse = topics.find(t => t.id === existingTopicId)!
        } else {
          // Create the topic with a random color
          const topicColor = PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)]
          topicToUse = await topicsApi.create({
            name: generatedTopic.name,
            description: generatedTopic.description,
            color: topicColor,
            use_newsapi: generatedTopic.use_newsapi,
          })
        }
        
        // Get all existing sites to check for duplicates
        const existingSitesData = await customSitesApi.list()
        const existingUrls = new Set(
          existingSitesData.sites.map(site => normalizeUrl(site.url))
        )
        
        // Create all sites (no selection needed - create all recommended sites)
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
        
        // Refresh topics and sites
        queryClient.invalidateQueries({ queryKey: ['topics'] })
        queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
        
        // Combine the prompt-generated topic with any pre-selected topics
        const finalTopicIds = selectedTopicIds.includes(topicToUse.id)
          ? selectedTopicIds  // Topic already selected, use all selected topics
          : [...selectedTopicIds, topicToUse.id]  // Add prompt topic to selected topics
        
        // Clear the prompt
        setTopicPrompt('')
        
        // Generate briefing with combined topics (prompt-generated + pre-selected)
        generateMutation.mutate({
          profileId: requestProfileId,
          topicIds: finalTopicIds.length > 0 ? finalTopicIds : undefined,
          castId: selectedCastId,
        })
      } else {
        // No prompt, just generate with selected topics
        generateMutation.mutate({
          profileId: requestProfileId,
          topicIds: selectedTopicIds.length > 0 ? selectedTopicIds : undefined,
          castId: selectedCastId,
        })
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create topic from prompt'
      setPromptError(errorMessage)
      setIsGenerating(false)
    }
  }
  
  return (
    <div className="card mb-6 sm:mb-8">
      <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-accent" />
        Generate New Briefing
      </h2>
      
       {/* Prompt Box for Creating New Topic */}
       <div className="mb-6">
         <div className="space-y-4">
           <div className="relative">
             <textarea
               value={topicPrompt}
               onChange={(e) => setTopicPrompt(e.target.value)}
               placeholder="e.g. I want to follow the latest developments in electric vehicles and sustainable transportation..."
               className="input min-h-[80px] sm:min-h-[100px] resize-none pr-4"
               disabled={isGenerating || generateMutation.isPending}
             />
           </div>
           
           {promptError && (
             <div className="flex items-center gap-2 text-red-400 text-sm">
               <AlertCircle className="w-4 h-4 flex-shrink-0" />
               <span>{promptError}</span>
             </div>
           )}
         </div>
       </div>
      
      {/* Existing Topics Selection */}
      <div className="mb-4">
        <div className="mb-2">
          <p className="text-sm text-augustus-400">Or select existing topics to include:</p>
        </div>
        {topicsLoading ? (
          <div className="flex items-center gap-2 text-augustus-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Loading topics...</span>
          </div>
        ) : topics.length === 0 ? (
          <p className="text-sm text-augustus-500">
            No topics found. <a href="/topics" className="text-accent hover:underline">Create some topics</a> first.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {topics.map((topic) => (
              <button
                key={topic.id}
                onClick={() => toggleTopic(topic.id)}
                className={clsx(
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5 min-h-[36px]',
                  selectedTopicIds.includes(topic.id)
                    ? 'text-white'
                    : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                )}
                style={selectedTopicIds.includes(topic.id) ? {
                  backgroundColor: topic.color || '#3B82F6',
                } : undefined}
              >
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: topic.color || '#3B82F6' }}
                />
                {topic.name}
              </button>
            ))}
          </div>
        )}
        {selectedTopicIds.length === 0 && topics.length > 0 && (
          <p className="text-sm text-augustus-500 mt-2">
            No topics selected - all topics will be included
          </p>
        )}
      </div>
      
      {/* Cast selector */}
      {casts.length > 1 && (
        <div className="mb-4">
          <div className="mb-2">
            <label className="text-sm text-augustus-400">
              Select cast:
            </label>
          </div>
          <select
            value={selectedCastId || ''}
            onChange={(e) => setSelectedCastId(e.target.value || undefined)}
            className="input w-full"
          >
            {casts.map((cast) => (
              <option key={cast.id} value={cast.id}>
                {cast.name}{cast.is_default ? ' ★' : ''}
              </option>
            ))}
          </select>
        </div>
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
        <div className="mb-6 space-y-3" aria-label="Generation queue">
          <p className="text-sm text-augustus-400">{activeBriefings.length} briefing{activeBriefings.length === 1 ? '' : 's'} in progress or queued. You can add more below.</p>
          {activeBriefings.map(briefing => {
            const generating = briefing.status === 'generating'
            const progress = briefing.extra_data?.progress
            const cancelling = cancellingIds.has(briefing.id)
            return (
              <div key={briefing.id} className={clsx('p-4 border rounded-lg', generating
                ? 'bg-yellow-500/10 border-yellow-500/20' : 'bg-blue-500/10 border-blue-500/30')}>
                <div className="flex items-start justify-between gap-3">
                  {generating ? <Loader2 className="w-5 h-5 animate-spin text-yellow-400 flex-shrink-0" />
                    : <Clock className="w-5 h-5 text-blue-400 flex-shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className={clsx('font-medium text-sm', generating ? 'text-yellow-400' : 'text-blue-400')}>
                      {generating ? 'Generating briefing…' : 'Queued for generation'}
                    </p>
                    <p className="text-sm text-augustus-400 truncate">{briefing.title}</p>
                    {!generating && <p className="text-xs text-blue-300/70 mt-1">Will start automatically in request order.</p>}
                    {generating && progress && (
                      <div className="mt-3 space-y-1">
                        <p className="text-xs text-augustus-400">{progress.step_name} · {progress.percent}%</p>
                        <div className="h-2 bg-augustus-800 rounded-full overflow-hidden">
                          <div className="h-full bg-yellow-500 rounded-full transition-all duration-500" style={{ width: `${progress.percent}%` }} />
                        </div>
                      </div>
                    )}
                  </div>
                  <button onClick={() => profileId && cancelMutation.mutate({ id: briefing.id, profileId })} disabled={cancelling}
                    className="btn btn-ghost p-2 text-augustus-400 hover:text-red-400 hover:bg-red-500/10 flex-shrink-0"
                    aria-label={`Cancel ${briefing.title}`} title="Cancel briefing">
                    {cancelling ? <Loader2 className="w-5 h-5 animate-spin" /> : <XCircle className="w-5 h-5" />}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

        <div className="space-y-3">
          <div>
            <p className="text-sm text-augustus-400">Generate your briefing:</p>
          </div>
           <button
             onClick={handleGenerate}
             disabled={isGenerating || generateMutation.isPending}
             className="btn btn-primary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
           >
             {(isGenerating || generateMutation.isPending) ? (
               <>
                 <Loader2 className="w-5 h-5 animate-spin" />
                 {topicPrompt.trim() ? 'Creating Topic & Starting...' : 'Starting...'}
               </>
             ) : (
               <>
                 <Sparkles className="w-5 h-5" />
                 {activeBriefings.length ? 'Queue Another Briefing' : 'Create Briefing Now'}
               </>
             )}
           </button>
           {topicPrompt.trim() && (
             <p className="text-sm text-augustus-500">
               This will create a new topic from your prompt and generate a briefing
             </p>
           )}
        </div>
    </div>
  )
}
