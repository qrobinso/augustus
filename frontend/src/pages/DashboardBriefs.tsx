import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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
  CheckCircle,
  Circle,
  XCircle,
  Tag,
  Waves,
  Heart
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, settingsApi, topicsApi, castsApi, Briefing, Topic, Cast } from '../api/client'
import { useStore } from '../store/useStore'
import { formatCompactDate } from '../utils/timezone'

export default function DashboardBriefs() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const currentAudio = useStore((s) => s.currentAudio)
  const isPlaying = useStore((s) => s.isPlaying)
  const playAudio = useStore((s) => s.playAudio)
  const togglePlayPause = useStore((s) => s.togglePlayPause)
  
  const [listenedFilter, setListenedFilter] = useState<boolean | undefined>(undefined)
  const [filterCastId, setFilterCastId] = useState<string | undefined>(undefined)
  const [filterTopicIds, setFilterTopicIds] = useState<string[]>([])
  const [favoriteFilter, setFavoriteFilter] = useState<boolean | undefined>(undefined)
  const [currentPage, setCurrentPage] = useState(0)
  const [isMobile, setIsMobile] = useState(false)
  const pageSize = 10
  
  // Detect mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 640)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])
  
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
    briefings?.some((b) => b.status === 'pending' || b.status === 'generating')
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['briefings', listenedFilter, filterCastId, filterTopicIds, favoriteFilter, currentPage],
    queryFn: () => briefingsApi.list(
      pageSize, 
      currentPage * pageSize, 
      listenedFilter,
      filterCastId,
      filterTopicIds.length > 0 ? filterTopicIds : undefined,
      favoriteFilter
    ),
    refetchInterval: (query) => {
      return hasBriefingInProgress(query.state.data?.briefings) ? 2000 : 10000
    },
  })
  
  // Reset to first page when filter changes
  useEffect(() => {
    setCurrentPage(0)
  }, [listenedFilter, filterCastId, filterTopicIds, favoriteFilter])
  
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
  
  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 1000 / 60)
    
    const dateInTz = new Date(dateStr)
    const nowInTz = new Date()
    
    const timeFormatter = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
    
    const dateFormatter = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      month: 'short',
      day: 'numeric',
    })
    
    const dateStrInTz = dateFormatter.format(dateInTz)
    const nowStrInTz = dateFormatter.format(nowInTz)
    
    if (dateStrInTz === nowStrInTz) {
      const timeStr = timeFormatter.format(dateInTz)
      if (diffMins < 1) {
        return `Just now (${timeStr})`
      }
      if (diffMins < 60) {
        return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago (${timeStr})`
      }
      return `at ${timeStr} today`
    }
    
    const yesterday = new Date(nowInTz)
    yesterday.setDate(yesterday.getDate() - 1)
    const yesterdayStr = dateFormatter.format(yesterday)
    if (dateStrInTz === yesterdayStr) {
      const timeStr = timeFormatter.format(dateInTz)
      return `at ${timeStr} yesterday`
    }
    
    const timeStr = timeFormatter.format(dateInTz)
    return `${dateFormatter.format(dateInTz)} at ${timeStr}`
  }

  // Helper function to render a briefing card
  const renderBriefingCard = (briefing: Briefing, isLatest: boolean, isCurrentlyPlaying: boolean, briefingTopics: Topic[]) => {
    if (isLatest) {
      return (
        <div
          key={briefing.id}
          onClick={() => navigate(`/briefing/${briefing.id}`)}
          className="relative group cursor-pointer overflow-hidden rounded-[2rem] bg-augustus-900 border border-augustus-800/50 shadow-2xl transition-all hover:border-augustus-700 active:scale-[0.99] min-h-[380px] sm:min-h-[450px] flex flex-col p-6 sm:p-10"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-accent/10 via-transparent to-transparent opacity-50" />
          <div className="absolute -right-20 -top-20 w-96 h-96 bg-accent/25 rounded-full blur-[100px] animate-spotlight pointer-events-none" />
          
          {briefing.chapters && briefing.chapters.length > 0 && (
            <div className="absolute inset-0 overflow-visible pointer-events-none">
              <div
                className="absolute font-black text-white uppercase tracking-tighter opacity-5 text-8xl sm:text-[12rem] top-1/2 -translate-y-1/2 left-0 -translate-x-8 w-[150%] text-left leading-[0.9]"
                style={{ textShadow: '0 0 20px rgba(255,255,255,0.1)' }}
              >
                {briefing.chapters.map(c => c.title).join(' ')}
              </div>
            </div>
          )}
          
          <div className="relative z-10 flex flex-col h-full justify-between flex-1">
            <div className="flex justify-between items-start mb-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-augustus-800 flex items-center justify-center border border-augustus-700 shadow-lg">
                  <Waves className="w-6 h-6 text-accent" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                    <p className="text-[10px] text-augustus-500 font-black">
                      Generated {formatRelativeTime(briefing.generated_at || briefing.created_at)}
                    </p>
                  </div>
                  {(briefing.extra_data?.cast_name as string) && (
                    <p className="text-white text-base font-bold">{(briefing.extra_data?.cast_name as string)}</p>
                  )}
                </div>
              </div>
              
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm('Are you sure you want to delete this briefing?')) {
                    deleteMutation.mutate(briefing.id)
                  }
                }}
                className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400 flex-shrink-0"
                title="Delete"
              >
                <Trash2 className="w-5 h-5 sm:w-6 sm:h-6" />
              </button>
            </div>

            <div className="mb-8 mt-2 sm:mt-4">
              <div className="flex flex-wrap gap-2 mb-6 sm:mb-8">
                {briefingTopics.map((topic) => (
                  <span
                    key={topic.id}
                    className="px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest bg-white/10 text-white/90 border border-white/10 backdrop-blur-md"
                  >
                    {topic.name}
                  </span>
                ))}
              </div>
              
              <h2 className="text-4xl sm:text-6xl font-display font-black text-white leading-[0.85] tracking-tighter group-hover:text-accent transition-colors">
                {briefing.title}
              </h2>
              
              {(briefing.status === 'generating' || briefing.status === 'pending') && briefing.extra_data?.progress && (
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between text-xs sm:text-sm">
                    <span className="text-augustus-300 truncate mr-2">
                      Step {briefing.extra_data.progress.step}/{briefing.extra_data.progress.total_steps}: {briefing.extra_data.progress.step_name}
                    </span>
                    <span className="text-augustus-400 flex-shrink-0">
                      {briefing.extra_data.progress.percent}%
                    </span>
                  </div>
                  <div className="h-2 bg-augustus-800/50 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-yellow-500 rounded-full transition-all duration-500"
                      style={{ width: `${briefing.extra_data.progress.percent}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {briefing.status === 'completed' && (briefing.extra_data as any)?.story_analysis ? (
              <div className="mt-auto flex flex-col sm:flex-row sm:items-end justify-between gap-6 sm:gap-8">
                <div className="flex-1">
                  <p className="text-base sm:text-lg text-augustus-300 leading-relaxed">
                    <span className="text-augustus-400">
                      {formatDateShort(briefing.created_at)} • {formatDurationLong(briefing.duration_seconds)} • 
                    </span>{' '}
                    <span className="text-augustus-200">
                      {(() => {
                        const summary = ((briefing.extra_data as any)?.story_analysis as string) || ''
                        const maxLength = 300
                        return summary.length > maxLength ? summary.substring(0, maxLength).trim() + '...' : summary
                      })()}
                    </span>
                  </p>
                </div>
                
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handlePlayPause(briefing, e)
                  }}
                  disabled={briefing.status !== 'completed'}
                  className={clsx(
                    'w-20 h-20 sm:w-28 sm:h-28 rounded-full flex items-center justify-center transition-all active:scale-95 flex-shrink-0 relative overflow-hidden group/btn shadow-2xl',
                    briefing.status === 'completed'
                      ? 'bg-accent hover:bg-accent-600 text-white hover:scale-105'
                      : 'bg-augustus-800 text-augustus-500'
                  )}
                >
                  <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent opacity-0 group-hover/btn:opacity-100 transition-opacity" />
                  {isCurrentlyPlaying ? (
                    <Pause className="w-10 h-10 sm:w-14 sm:h-14 fill-current relative z-10" />
                  ) : (
                    <Play className="w-10 h-10 sm:w-14 sm:h-14 fill-current ml-1.5 relative z-10" />
                  )}
                </button>
              </div>
            ) : (
              <div className="mt-auto flex flex-col sm:flex-row sm:items-end justify-between gap-8">
                <div className="flex gap-12 items-end flex-1 min-w-0">
                  <div className="flex flex-col">
                    <div className="h-[2em] sm:h-[2.5em] flex items-end">
                      <span className="text-4xl sm:text-5xl font-black text-white leading-none tracking-tighter">
                        {formatDuration(briefing.duration_seconds)}
                      </span>
                    </div>
                    <span className="text-[9px] uppercase tracking-[0.2em] text-augustus-500 font-black mt-3">Duration</span>
                  </div>
                  
                  <div className="hidden sm:flex flex-col">
                    <div className="h-[2.5em] flex items-end">
                      <span className="text-4xl sm:text-5xl font-black text-white leading-none tracking-tighter uppercase">
                        {new Intl.DateTimeFormat('en-US', { timeZone: timezone, month: 'short', day: 'numeric' }).format(new Date(briefing.created_at))}
                      </span>
                    </div>
                    <span className="text-[9px] uppercase tracking-[0.2em] text-augustus-500 font-black mt-3">Released</span>
                  </div>
                </div>

                <button
                  onClick={(e) => handlePlayPause(briefing, e)}
                  disabled={briefing.status !== 'completed'}
                  className={clsx(
                    'w-20 h-20 sm:w-28 sm:h-28 rounded-full flex items-center justify-center transition-all active:scale-95 flex-shrink-0 relative overflow-hidden group/btn shadow-2xl',
                    briefing.status === 'completed'
                      ? 'bg-accent hover:bg-accent-600 text-white hover:scale-105'
                      : 'bg-augustus-800 text-augustus-500'
                  )}
                >
                  <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent opacity-0 group-hover/btn:opacity-100 transition-opacity" />
                  {briefing.status === 'generating' || briefing.status === 'pending' ? (
                    <Loader2 className="w-10 h-10 animate-spin" />
                  ) : isCurrentlyPlaying ? (
                    <Pause className="w-10 h-10 sm:w-14 sm:h-14 fill-current relative z-10" />
                  ) : (
                    <Play className="w-10 h-10 sm:w-14 sm:h-14 fill-current ml-1.5 relative z-10" />
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )
    }

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
      </div>
    )
  }

  return (
    <div className="space-y-3 sm:space-y-4">
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
            {favoriteFilter === true
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
          const shouldGroupByListened = listenedFilter === undefined
          const briefings = data?.briefings || []
          
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
                      const isLatest = isMobile && notListened.length > 0
                      const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
                      const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
                      
                      return renderBriefingCard(briefing, isLatest, isCurrentlyPlaying, briefingTopics)
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
                      const isLatest = false
                      const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
                      const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
                      
                      return renderBriefingCard(briefing, isLatest, isCurrentlyPlaying, briefingTopics)
                    })}
                  </>
                )}
              </>
            )
          } else {
            return briefings.map((briefing) => {
              const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
              const isLatest = isMobile && !briefing.listened
              const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
              const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
              
              return renderBriefingCard(briefing, isLatest, isCurrentlyPlaying, briefingTopics)
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

