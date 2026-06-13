import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Pause,
  Loader2,
  Clock,
  Calendar,
  Trash2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  Circle,
  XCircle,
  Tag,
  Heart,
  ListPlus,
  CornerUpRight,
  Search,
  ListMusic
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, settingsApi, topicsApi, castsApi, Briefing, Topic, Cast } from '../api/client'
import { useStore } from '../store/useStore'
import type { QueueItem } from '../store/queue'
import { formatCompactDate } from '../utils/timezone'
import { useProfileNavigate } from '../utils/profileSlug'

export default function DashboardBriefs() {
  const navigate = useProfileNavigate()
  const queryClient = useQueryClient()
  const currentAudio = useStore((s) => s.currentAudio)
  const isPlaying = useStore((s) => s.isPlaying)
  const playAudio = useStore((s) => s.playAudio)
  const togglePlayPause = useStore((s) => s.togglePlayPause)
  const addToQueue = useStore((s) => s.addToQueue)
  const playNext = useStore((s) => s.playNext)
  const clearQueue = useStore((s) => s.clearQueue)

  const toQueueItem = (b: Briefing): QueueItem => ({
    id: b.id,
    type: 'briefing',
    title: b.title,
    audioUrl: b.audio_url!,
    transcript: b.transcript,
    chapters: b.chapters,
  })
  
  const [listenedFilter, setListenedFilter] = useState<boolean | undefined>(undefined)
  const [filterCastId, setFilterCastId] = useState<string | undefined>(undefined)
  const [filterTopicIds, setFilterTopicIds] = useState<string[]>([])
  const [favoriteFilter, setFavoriteFilter] = useState<boolean | undefined>(undefined)
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 10

  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  // User-chosen play order for Today's Stack (ids; session-local)
  const [stackOrder, setStackOrder] = useState<string[]>([])

  useEffect(() => {
    const t = setTimeout(() => setSearchQuery(searchInput), 300)
    return () => clearTimeout(t)
  }, [searchInput])
  
  // Filters accordion state - persisted to localStorage
  const [filtersExpanded, setFiltersExpanded] = useState(() => {
    const saved = localStorage.getItem('filtersExpanded')
    return saved !== null ? JSON.parse(saved) : false
  })
  
  useEffect(() => {
    localStorage.setItem('filtersExpanded', JSON.stringify(filtersExpanded))
  }, [filtersExpanded])
  
  // Check if there's a briefing in progress to determine poll interval
  const hasBriefingInProgress = (briefings: Briefing[] | undefined) => 
    briefings?.some((b) => b.status === 'pending' || b.status === 'generating' || b.status === 'queued')
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['briefings', listenedFilter, filterCastId, filterTopicIds, favoriteFilter, currentPage, searchQuery],
    queryFn: () => briefingsApi.list(
      pageSize,
      currentPage * pageSize,
      listenedFilter,
      filterCastId,
      filterTopicIds.length > 0 ? filterTopicIds : undefined,
      favoriteFilter,
      searchQuery || undefined
    ),
    refetchInterval: (query) => {
      return hasBriefingInProgress(query.state.data?.briefings) ? 2000 : 10000
    },
  })
  
  // Reset to first page when filter or search changes
  useEffect(() => {
    setCurrentPage(0)
  }, [listenedFilter, filterCastId, filterTopicIds, favoriteFilter, searchQuery])

  // Today's Stack: unplayed briefings (incl. in-progress), independent of archive filters/paging
  const { data: stackData } = useQuery({
    queryKey: ['briefings', 'stack'],
    queryFn: () => briefingsApi.list(20, 0, false),
    refetchInterval: (query) => {
      return hasBriefingInProgress(query.state.data?.briefings) ? 2000 : 10000
    },
  })

  const stack = useMemo(() => {
    // Failed/cancelled briefs stay out of the stack; they're handled in the archive
    const briefings = (stackData?.briefings || []).filter(
      (b) =>
        (b.status === 'completed' && b.audio_url) ||
        b.status === 'pending' ||
        b.status === 'generating' ||
        b.status === 'queued'
    )
    const byId = new Map(briefings.map((b) => [b.id, b]))
    const ordered: Briefing[] = []
    for (const id of stackOrder) {
      const b = byId.get(id)
      if (b) {
        ordered.push(b)
        byId.delete(id)
      }
    }
    for (const b of briefings) {
      if (byId.has(b.id)) ordered.push(b)
    }
    return ordered
  }, [stackData?.briefings, stackOrder])

  const stackPlayable = stack.filter((b) => b.status === 'completed' && b.audio_url)
  const stackTotalMins = Math.round(
    stackPlayable.reduce((sum, b) => {
      const remaining = (b.duration_seconds || 0) - (b.playback_position || 0)
      return sum + Math.max(0, remaining)
    }, 0) / 60
  )

  const moveStackItem = (id: string, direction: -1 | 1) => {
    const ids = stack.map((b) => b.id)
    const from = ids.indexOf(id)
    const to = from + direction
    if (from < 0 || to < 0 || to >= ids.length) return
    const next = [...ids]
    ;[next[from], next[to]] = [next[to], next[from]]
    setStackOrder(next)
  }

  const handlePlayAll = () => {
    if (stackPlayable.length === 0) return
    const [first, ...rest] = stackPlayable
    playAudio({
      ...toQueueItem(first),
      initialPosition: first.playback_position || undefined,
    })
    clearQueue()
    rest.forEach((b) => addToQueue(toQueueItem(b)))
  }

  const hasActiveFilters =
    listenedFilter !== undefined ||
    filterCastId !== undefined ||
    filterTopicIds.length > 0 ||
    favoriteFilter !== undefined
  
  // Fetch settings for timezone
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })
  
  // Fetch topics for filters
  const { data: topicsData } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  // Fetch casts for filters
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  const topics = topicsData?.topics || []
  const casts = castsData?.casts || []
  // Use user's timezone if available, fallback to browser's timezone
  const timezone = (settings?.timezone && settings.timezone.trim()) || Intl.DateTimeFormat().resolvedOptions().timeZone
  
  const deleteMutation = useMutation({
    mutationFn: (id: string) => briefingsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
  })
  
  const handlePlayPause = (briefing: Briefing, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (!briefing.audio_url) return
    
    if (currentAudio?.id === briefing.id) {
      togglePlayPause()
    } else {
      playAudio({
        id: briefing.id,
        type: 'briefing',
        title: briefing.title,
        audioUrl: briefing.audio_url,
        transcript: briefing.transcript,
        chapters: briefing.chapters,
        initialPosition: briefing.playback_position || undefined,
      })
    }
  }
  
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--:--'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }
  
  const formatDurationLong = (seconds?: number) => {
    if (!seconds) return '-- min -- sec'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins} min ${secs} sec`
  }
  
  const formatDateShort = (dateStr: string) => {
    const date = new Date(dateStr)
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
    return formatter.format(date)
  }
  
  const formatDate = (dateStr: string) => {
    return formatCompactDate(dateStr, timezone)
  }
  
  // Helper function to render a briefing card
  const renderBriefingCard = (briefing: Briefing, isCurrentlyPlaying: boolean, briefingTopics: Topic[]) => {
    const isLatest = false
    return (
      <div
        key={briefing.id}
        onClick={() => navigate(`/briefing/${briefing.id}`)}
        className={clsx(
          'card hover:border-augustus-600 transition-colors cursor-pointer group active:scale-[0.99] relative',
          isLatest && 'p-6 sm:p-8'
        )}
      >
         <div className={clsx(
           'flex flex-col',
           briefing.status === 'completed' && 'pl-14 sm:pl-16'
         )}>
           {briefingTopics.length > 0 && (
            <div className={clsx('flex flex-wrap gap-1.5 sm:gap-2', isLatest ? 'mb-3 sm:mb-4' : 'mb-2')}>
              {briefingTopics.slice(0, isLatest ? briefingTopics.length : (window.innerWidth < 640 ? 2 : briefingTopics.length)).map((topic) => (
                <span
                  key={topic.id}
                  className={clsx(
                    'rounded-full font-medium flex items-center gap-1.5',
                    isLatest ? 'px-3 py-1.5 text-sm sm:text-base' : 'px-1.5 sm:px-2 py-0.5 text-xs'
                  )}
                  style={{ backgroundColor: `${topic.color || '#3B82F6'}20`, color: topic.color || '#3B82F6' }}
                >
                  <span
                    className={clsx('rounded-full', isLatest ? 'w-2 h-2 sm:w-2.5 sm:h-2.5' : 'w-1.5 h-1.5 hidden sm:block')}
                    style={{ backgroundColor: topic.color || '#3B82F6' }}
                  />
                  {topic.name}
                </span>
              ))}
              {!isLatest && briefingTopics.length > 2 && window.innerWidth < 640 && (
                <span className="text-xs text-augustus-500">+{briefingTopics.length - 2}</span>
              )}
            </div>
          )}
          
          <h3 className={clsx(
            'font-semibold text-white truncate group-hover:text-accent transition-colors mb-2',
            isLatest ? 'text-lg sm:text-2xl' : 'text-sm sm:text-base'
          )}>
            {briefing.title}
          </h3>
          
          {briefing.status === 'completed' && (briefing.extra_data as any)?.story_analysis ? (
            <div className="space-y-1">
              <p className={clsx(
                'text-augustus-300 leading-relaxed',
                isLatest ? 'text-base sm:text-lg' : 'text-sm sm:text-base'
              )}>
                <span className="text-augustus-400">
                  {formatDateShort(briefing.created_at)} • {formatDurationLong(briefing.duration_seconds)} • 
                </span>{' '}
                <span className="text-augustus-200">
                  {(() => {
                    const summary = ((briefing.extra_data as any)?.story_analysis as string) || ''
                    const maxLength = isLatest ? 300 : 200
                    return summary.length > maxLength ? summary.substring(0, maxLength).trim() + '...' : summary
                  })()}
                </span>
              </p>
            </div>
          ) : (
            <div className={clsx(
              'flex flex-wrap items-center gap-x-2 gap-y-1 text-augustus-500',
              isLatest ? 'text-sm sm:text-base' : 'text-xs sm:text-sm'
            )}>
              <span className="flex items-center gap-1.5">
                <Clock className={clsx(isLatest ? 'w-4 h-4 sm:w-5 sm:h-5' : 'w-3.5 h-3.5')} />
                {formatDuration(briefing.duration_seconds)}
              </span>
              <span className="flex items-center gap-1.5">
                <Calendar className={clsx(isLatest ? 'w-4 h-4 sm:w-5 sm:h-5' : 'w-3.5 h-3.5')} />
                {formatDate(briefing.created_at)}
              </span>
              {briefing.status === 'completed' && (
                <span className={clsx(
                  'flex items-center gap-1.5 px-2 py-0.5 rounded-full font-medium',
                  isLatest ? 'text-sm sm:text-base' : 'text-xs',
                  briefing.listened 
                    ? 'bg-accent/20 text-accent' 
                    : 'bg-augustus-700 text-augustus-400'
                )}>
                  {briefing.listened ? (
                    <CheckCircle className={clsx(isLatest ? 'w-4 h-4 sm:w-5 sm:h-5' : 'w-3 h-3')} />
                  ) : (
                    <Circle className={clsx(isLatest ? 'w-4 h-4 sm:w-5 sm:h-5' : 'w-3 h-3')} />
                  )}
                  <span className={isLatest ? '' : 'hidden sm:inline'}>{briefing.listened ? 'Listened' : 'Not Listened'}</span>
                </span>
              )}
            </div>
          )}
          
          {briefing.error_message && (
            <p className={clsx('text-red-400 mt-2', isLatest ? 'text-sm sm:text-base' : 'text-xs sm:text-sm')}>{briefing.error_message}</p>
          )}
          
          {briefing.status === 'queued' && (
            <div className={clsx('mt-2 p-2 bg-blue-500/10 border border-blue-500/30 rounded-lg', isLatest && 'mt-3')}>
              <div className="flex items-center gap-2 text-blue-400">
                <Clock className="w-3.5 h-3.5" />
                <span className="text-xs font-medium">Queued - waiting for other generation to complete</span>
              </div>
            </div>
          )}
          
          {(briefing.status === 'generating' || briefing.status === 'pending') && briefing.extra_data?.progress && (
            <div className={clsx('space-y-1 sm:space-y-2 mt-2', isLatest && 'mt-3 sm:mt-4')}>
              <div className="flex justify-between text-xs">
                <span className="text-augustus-400 truncate mr-2">
                  Step {briefing.extra_data.progress.step}/{briefing.extra_data.progress.total_steps}: {briefing.extra_data.progress.step_name}
                </span>
                <span className="text-augustus-500 flex-shrink-0">
                  {briefing.extra_data.progress.percent}%
                </span>
              </div>
              <div className="h-2 bg-augustus-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-yellow-500 rounded-full transition-all duration-500"
                  style={{ width: `${briefing.extra_data.progress.percent}%` }}
                />
              </div>
            </div>
          )}
        </div>
        
         {briefing.status === 'completed' && (
           <button
             onClick={(e) => {
               e.stopPropagation()
               handlePlayPause(briefing, e)
             }}
             className={clsx(
               'absolute top-4 left-4 rounded-full flex items-center justify-center flex-shrink-0 transition-all z-10',
               isLatest 
                 ? 'w-12 h-12 sm:w-14 sm:h-14'
                 : 'w-10 h-10 sm:w-12 sm:h-12',
               isCurrentlyPlaying
                 ? 'bg-accent hover:bg-accent-600 text-white glow'
                 : 'bg-augustus-800/80 hover:bg-augustus-700 text-augustus-300 hover:text-white backdrop-blur-sm'
             )}
           >
             {isCurrentlyPlaying ? (
               <Pause className={clsx(isLatest ? 'w-6 h-6 sm:w-7 sm:h-7' : 'w-5 h-5 sm:w-6 sm:h-6')} />
             ) : (
               <Play className={clsx(isLatest ? 'w-6 h-6 sm:w-7 sm:h-7' : 'w-5 h-5 sm:w-6 sm:h-6', 'ml-0.5 sm:ml-1')} />
             )}
           </button>
         )}
         
         {/* Queue action buttons for completed briefings with audio */}
         {briefing.status === 'completed' && briefing.audio_url && (
           <div className="absolute top-4 right-4 flex items-center gap-1 z-10">
             <button
               onClick={(e) => {
                 e.stopPropagation()
                 playNext(toQueueItem(briefing))
               }}
               className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[36px] min-w-[36px] text-augustus-400 hover:text-white backdrop-blur-sm"
               title="Play next"
               aria-label="Play next"
             >
               <CornerUpRight className="w-4 h-4 sm:w-5 sm:h-5" />
             </button>
             <button
               onClick={(e) => {
                 e.stopPropagation()
                 addToQueue(toQueueItem(briefing))
               }}
               className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[36px] min-w-[36px] text-augustus-400 hover:text-white backdrop-blur-sm"
               title="Add to queue"
               aria-label="Add to queue"
             >
               <ListPlus className="w-4 h-4 sm:w-5 sm:h-5" />
             </button>
           </div>
         )}

         {/* Delete button for failed, cancelled, or errored briefings */}
         {(briefing.status === 'failed' || briefing.status === 'cancelled' || briefing.error_message) && (
           <button
             onClick={(e) => {
               e.stopPropagation()
               const statusText = briefing.status === 'cancelled' ? 'cancelled' : 'failed'
               if (confirm(`Are you sure you want to delete this ${statusText} briefing?`)) {
                 deleteMutation.mutate(briefing.id)
               }
             }}
             className="absolute top-4 right-4 w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center flex-shrink-0 transition-all z-10 bg-red-500/20 hover:bg-red-500/40 text-red-400 hover:text-red-300 backdrop-blur-sm"
             title="Delete briefing"
           >
             <Trash2 className="w-5 h-5 sm:w-6 sm:h-6" />
           </button>
         )}
      </div>
    )
  }

  return (
    <div className="space-y-3 sm:space-y-4">
      {/* Today's Stack — curated unplayed queue, hidden while searching/filtering */}
      {!searchQuery.trim() && !hasActiveFilters && stack.length > 0 && (
        <div className="card p-0 overflow-hidden mb-6 sm:mb-8">
          <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 border-b border-augustus-800/60">
            <div className="min-w-0">
              <h2 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
                <ListMusic className="w-5 h-5 text-accent" />
                Today's Stack
              </h2>
              <p className="text-xs sm:text-sm text-augustus-500 mt-0.5">
                {stackPlayable.length} brief{stackPlayable.length === 1 ? '' : 's'} · {stackTotalMins} min left
              </p>
            </div>
            <button
              onClick={handlePlayAll}
              disabled={stackPlayable.length === 0}
              className="btn btn-primary flex items-center gap-2 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px]"
            >
              <Play className="w-4 h-4 fill-current" />
              Play all
            </button>
          </div>
          <ol>
            {stack.map((briefing, index) => {
              const isCurrent = currentAudio?.id === briefing.id
              const isCurrentlyPlaying = isCurrent && isPlaying
              const inProgress = briefing.status === 'pending' || briefing.status === 'generating'
              const queued = briefing.status === 'queued'
              const playable = briefing.status === 'completed' && !!briefing.audio_url
              const firstTopicId = ((briefing.extra_data?.topic_ids as string[]) || [])[0]
              const firstTopic = topics.find((t) => t.id === firstTopicId)
              const minsLeft =
                playable && briefing.playback_position && briefing.duration_seconds
                  ? Math.max(1, Math.ceil((briefing.duration_seconds - briefing.playback_position) / 60))
                  : null
              const progressPercent =
                playable && briefing.playback_position && briefing.duration_seconds
                  ? Math.min(100, (briefing.playback_position / briefing.duration_seconds) * 100)
                  : null

              return (
                <li
                  key={briefing.id}
                  onClick={() => navigate(`/briefing/${briefing.id}`)}
                  className={clsx(
                    'group flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 border-b border-augustus-800/40 last:border-b-0 cursor-pointer transition-colors hover:bg-augustus-800/30',
                    isCurrent && 'bg-accent/5'
                  )}
                >
                  <span className="w-5 text-center text-xs font-mono text-augustus-500 flex-shrink-0">
                    {index + 1}
                  </span>
                  <button
                    onClick={(e) => handlePlayPause(briefing, e)}
                    disabled={!playable}
                    className={clsx(
                      'w-10 h-10 sm:w-11 sm:h-11 rounded-full flex items-center justify-center flex-shrink-0 transition-all',
                      isCurrentlyPlaying
                        ? 'bg-accent text-white'
                        : playable
                        ? 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 hover:text-white'
                        : 'bg-augustus-800/50 text-augustus-500'
                    )}
                    aria-label={isCurrentlyPlaying ? 'Pause' : 'Play'}
                  >
                    {inProgress ? (
                      <Loader2 className="w-4 h-4 animate-spin text-yellow-400" />
                    ) : queued ? (
                      <Clock className="w-4 h-4 text-blue-400" />
                    ) : isCurrentlyPlaying ? (
                      <Pause className="w-4 h-4 fill-current" />
                    ) : (
                      <Play className="w-4 h-4 fill-current ml-0.5" />
                    )}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className={clsx(
                      'text-sm sm:text-base font-medium truncate transition-colors',
                      isCurrent ? 'text-accent' : 'text-white group-hover:text-accent'
                    )}>
                      {briefing.title}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-augustus-500 mt-0.5">
                      {firstTopic && (
                        <span className="flex items-center gap-1 truncate">
                          <span
                            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                            style={{ backgroundColor: firstTopic.color || '#3B82F6' }}
                          />
                          {firstTopic.name}
                        </span>
                      )}
                      {inProgress && briefing.extra_data?.progress ? (
                        <span className="text-yellow-400 truncate">
                          {briefing.extra_data.progress.step_name} · {briefing.extra_data.progress.percent}%
                        </span>
                      ) : queued ? (
                        <span className="text-blue-400">Queued</span>
                      ) : minsLeft !== null ? (
                        <span className="text-accent font-medium">{minsLeft} min left</span>
                      ) : (
                        <span>{formatDuration(briefing.duration_seconds)}</span>
                      )}
                    </div>
                    {progressPercent !== null && (
                      <div className="h-0.5 bg-augustus-800 rounded-full overflow-hidden mt-1.5 max-w-[200px]">
                        <div
                          className="h-full bg-accent rounded-full"
                          style={{ width: `${progressPercent}%` }}
                        />
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => moveStackItem(briefing.id, -1)}
                      disabled={index === 0}
                      className="p-1 text-augustus-500 hover:text-white disabled:opacity-30 disabled:hover:text-augustus-500 transition-colors"
                      aria-label="Move up"
                    >
                      <ChevronUp className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => moveStackItem(briefing.id, 1)}
                      disabled={index === stack.length - 1}
                      className="p-1 text-augustus-500 hover:text-white disabled:opacity-30 disabled:hover:text-augustus-500 transition-colors"
                      aria-label="Move down"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                  </div>
                </li>
              )
            })}
          </ol>
        </div>
      )}

      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-augustus-500 pointer-events-none" />
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search briefings…"
          className="w-full bg-augustus-900 border border-augustus-800 rounded-xl pl-10 pr-10 py-2.5 text-sm text-white placeholder-augustus-500 focus:outline-none focus:border-accent transition-colors"
          aria-label="Search briefings"
        />
        {searchInput && (
          <button
            onClick={() => setSearchInput('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-white transition-colors"
            aria-label="Clear search"
          >
            <XCircle className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Filter controls */}
      <div className="card mb-6 sm:mb-8">
        <button
          onClick={() => setFiltersExpanded(!filtersExpanded)}
          className="w-full flex items-center justify-between gap-2 text-left"
        >
          <h2 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
            <Tag className="w-5 h-5 text-accent" />
            Filters
            {(listenedFilter !== undefined || filterCastId !== undefined || filterTopicIds.length > 0 || favoriteFilter !== undefined) && (
              <span className="text-xs sm:text-sm font-normal text-augustus-500">
                (Active)
              </span>
            )}
          </h2>
          <ChevronDown 
            className={clsx(
              'w-5 h-5 text-augustus-400 transition-transform duration-200',
              filtersExpanded && 'rotate-180'
            )}
          />
        </button>
        
        {filtersExpanded && (
          <div className="mt-3 sm:mt-4">
            <div className="flex flex-col gap-3 sm:gap-2.5">
              {/* Listened filter */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <span className="text-xs sm:text-sm font-medium text-augustus-300 flex-shrink-0 sm:w-16">Status</span>
                <div className="flex items-center gap-2 overflow-x-auto scroll-smooth pb-1 sm:pb-0 -mx-1 px-1 sm:mx-0 sm:px-0">
                  <button
                    onClick={() => setListenedFilter(undefined)}
                    className={clsx(
                      'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0',
                      'min-h-[44px] sm:min-h-[32px] flex items-center justify-center',
                      'active:scale-95',
                      listenedFilter === undefined
                        ? 'bg-accent text-white shadow-lg shadow-accent/20'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                    )}
                  >
                    All
                  </button>
                  <button
                    onClick={() => setListenedFilter(true)}
                    className={clsx(
                      'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 whitespace-nowrap flex-shrink-0',
                      'min-h-[44px] sm:min-h-[32px] justify-center',
                      'active:scale-95',
                      listenedFilter === true
                        ? 'bg-accent text-white shadow-lg shadow-accent/20'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                    )}
                  >
                    <CheckCircle className="w-4 h-4 sm:w-3 sm:h-3" />
                    <span>Listened</span>
                  </button>
                  <button
                    onClick={() => setListenedFilter(false)}
                    className={clsx(
                      'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 whitespace-nowrap flex-shrink-0',
                      'min-h-[44px] sm:min-h-[32px] justify-center',
                      'active:scale-95',
                      listenedFilter === false
                        ? 'bg-accent text-white shadow-lg shadow-accent/20'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                    )}
                  >
                    <Circle className="w-4 h-4 sm:w-3 sm:h-3" />
                    <span>Not Listened</span>
                  </button>
                </div>
              </div>
              
              {/* Favorites filter */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <span className="text-xs sm:text-sm font-medium text-augustus-300 flex-shrink-0 sm:w-16">Favorites</span>
                <div className="flex items-center gap-2 overflow-x-auto scroll-smooth pb-1 sm:pb-0 -mx-1 px-1 sm:mx-0 sm:px-0">
                  <button
                    onClick={() => setFavoriteFilter(undefined)}
                    className={clsx(
                      'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0',
                      'min-h-[44px] sm:min-h-[32px] flex items-center justify-center',
                      'active:scale-95',
                      favoriteFilter === undefined
                        ? 'bg-accent text-white shadow-lg shadow-accent/20'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                    )}
                  >
                    All
                  </button>
                  <button
                    onClick={() => setFavoriteFilter(true)}
                    className={clsx(
                      'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 whitespace-nowrap flex-shrink-0',
                      'min-h-[44px] sm:min-h-[32px] justify-center',
                      'active:scale-95',
                      favoriteFilter === true
                        ? 'bg-accent text-white shadow-lg shadow-accent/20'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                    )}
                  >
                    <Heart className={clsx('w-4 h-4 sm:w-3 sm:h-3', favoriteFilter === true && 'fill-current')} />
                    <span>Favorites</span>
                  </button>
                </div>
              </div>
              
              {/* Cast filter */}
              {casts.length > 0 && (
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <span className="text-xs sm:text-sm font-medium text-augustus-300 flex-shrink-0 sm:w-16">Cast</span>
                  <div className="flex items-center gap-2 overflow-x-auto scroll-smooth pb-1 sm:pb-0 -mx-1 px-1 sm:mx-0 sm:px-0">
                    <button
                      onClick={() => setFilterCastId(undefined)}
                      className={clsx(
                        'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0',
                        'min-h-[44px] sm:min-h-[32px] flex items-center justify-center',
                        'active:scale-95',
                        filterCastId === undefined
                          ? 'bg-accent text-white shadow-lg shadow-accent/20'
                          : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                      )}
                    >
                      All Casts
                    </button>
                    {casts.map((cast: Cast) => (
                      <button
                        key={cast.id}
                        onClick={() => setFilterCastId(cast.id)}
                        className={clsx(
                          'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0',
                          'min-h-[44px] sm:min-h-[32px] flex items-center justify-center',
                          'active:scale-95',
                          filterCastId === cast.id
                            ? 'bg-accent text-white shadow-lg shadow-accent/20'
                            : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                        )}
                      >
                        {cast.name}{cast.is_default ? ' ★' : ''}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Topics filter */}
              {topics.length > 0 && (
                <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                  <span className="text-xs sm:text-sm font-medium text-augustus-300 flex-shrink-0 sm:w-16 sm:pt-1.5">Topics</span>
                  <div className="flex flex-wrap items-center gap-2 overflow-x-auto scroll-smooth pb-1 sm:pb-0 -mx-1 px-1 sm:mx-0 sm:px-0">
                    <button
                      onClick={() => setFilterTopicIds([])}
                      className={clsx(
                        'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0',
                        'min-h-[44px] sm:min-h-[32px] flex items-center justify-center',
                        'active:scale-95',
                        filterTopicIds.length === 0
                          ? 'bg-accent text-white shadow-lg shadow-accent/20'
                          : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                      )}
                    >
                      All Topics
                    </button>
                    {topics.map((topic: Topic) => (
                      <button
                        key={topic.id}
                        onClick={() => {
                          setFilterTopicIds((prev) =>
                            prev.includes(topic.id)
                              ? prev.filter((id) => id !== topic.id)
                              : [...prev, topic.id]
                          )
                        }}
                        className={clsx(
                          'px-3 sm:px-3 py-2 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 whitespace-nowrap flex-shrink-0',
                          'min-h-[44px] sm:min-h-[32px] justify-center',
                          'active:scale-95',
                          filterTopicIds.includes(topic.id)
                            ? 'text-white shadow-lg'
                            : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                        )}
                        style={filterTopicIds.includes(topic.id) ? {
                          backgroundColor: topic.color || '#3B82F6',
                          boxShadow: `0 4px 14px 0 ${topic.color || '#3B82F6'}40`,
                        } : undefined}
                      >
                        <span
                          className="w-2.5 h-2.5 sm:w-2 sm:h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: topic.color || '#3B82F6' }}
                        />
                        {topic.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Clear filters button */}
              {(listenedFilter !== undefined || filterCastId !== undefined || filterTopicIds.length > 0 || favoriteFilter !== undefined) && (
                <button
                  onClick={() => {
                    setListenedFilter(undefined)
                    setFilterCastId(undefined)
                    setFilterTopicIds([])
                    setFavoriteFilter(undefined)
                  }}
                  className="sm:hidden px-4 py-2 rounded-lg text-xs font-medium bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600 transition-all active:scale-95 flex items-center justify-center gap-1.5 min-h-[44px] border border-augustus-700"
                >
                  <XCircle className="w-4 h-4" />
                  Clear All Filters
                </button>
              )}
            </div>
          </div>
        )}
      </div>
      
      {isLoading ? (
        <div className="card flex items-center justify-center py-10 sm:py-12">
          <Loader2 className="w-8 h-8 animate-spin text-accent" />
        </div>
      ) : error ? (
        <div className="card text-center py-10 sm:py-12">
          <AlertCircle className="w-10 sm:w-12 h-10 sm:h-12 text-red-500 mx-auto mb-3 sm:mb-4" />
          <p className="text-sm sm:text-base text-augustus-400">Failed to load briefings. Is the backend running?</p>
        </div>
      ) : data?.briefings.length === 0 ? (
        <div className="card text-center py-10 sm:py-12">
          <Calendar className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
          <p className="text-sm sm:text-base text-augustus-400">
            {searchQuery.trim()
              ? `No briefings match "${searchQuery}"`
              : favoriteFilter === true
              ? 'No favorite briefings found.'
              : listenedFilter === true
              ? 'No listened briefings found.'
              : listenedFilter === false
              ? 'No Not Listened briefings found.'
              : 'No briefings yet. Generate your first one!'}
          </p>
        </div>
      ) : (
        (() => {
          const briefings = data?.briefings || []

          // When searching, render a flat list without grouping
          if (searchQuery.trim()) {
            return briefings.map((briefing) => {
              const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
              const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
              const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
              return renderBriefingCard(briefing, isCurrentlyPlaying, briefingTopics)
            })
          }

          const shouldGroupByListened = listenedFilter === undefined

          if (shouldGroupByListened) {
            const notListened = briefings.filter(b => !b.listened)
            const listened = briefings.filter(b => b.listened)
            
            return (
              <>
                {notListened.length > 0 && (
                  <>
                    <div className="sticky top-0 z-30 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 sm:py-4 mb-4 sm:mb-6 bg-augustus-950/95 backdrop-blur-sm border-b border-augustus-800/50">
                      <div className="flex items-center gap-2">
                        <Circle className="w-5 h-5 text-augustus-400" />
                        <h2 className="text-base sm:text-lg font-semibold text-white">
                          Unplayed ({notListened.length})
                        </h2>
                      </div>
                    </div>
                    {notListened.map((briefing) => {
                      const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
                      const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
                      const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
                      
                      return renderBriefingCard(briefing, isCurrentlyPlaying, briefingTopics)
                    })}
                  </>
                )}
                
                {listened.length > 0 && (
                  <>
                    <div className={clsx(
                      "sticky top-0 z-30 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 sm:py-4 mb-4 sm:mb-6 bg-augustus-950/95 backdrop-blur-sm border-b border-augustus-800/50",
                      notListened.length > 0 && "mt-6 sm:mt-8"
                    )}>
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-accent" />
                        <h2 className="text-base sm:text-lg font-semibold text-white">
                          Listened
                        </h2>
                      </div>
                    </div>
                    {listened.map((briefing) => {
                      const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
                      const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
                      const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
                      
                      return renderBriefingCard(briefing, isCurrentlyPlaying, briefingTopics)
                    })}
                  </>
                )}
              </>
            )
          } else {
            return briefings.map((briefing) => {
              const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
              const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
              const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
              
              return renderBriefingCard(briefing, isCurrentlyPlaying, briefingTopics)
            })
          }
        })()
      )}
      
      {/* Pagination */}
      {data && data.total > pageSize && (
        <div className="card mt-3 sm:mt-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
            <span className="text-xs sm:text-sm text-augustus-400">
              {currentPage * pageSize + 1}-{Math.min((currentPage + 1) * pageSize, data.total)} of {data.total}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                disabled={currentPage === 0}
                className="btn btn-ghost px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage((p) => p + 1)}
                disabled={(currentPage + 1) * pageSize >= data.total}
                className="btn btn-ghost px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

