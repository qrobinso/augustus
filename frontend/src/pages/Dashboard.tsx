import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play,
  Pause,
  Loader2, 
  Sparkles, 
  Clock, 
  Calendar,
  Trash2,
  AlertCircle,
  FileText,
  ChevronRight,
  ChevronDown,
  CheckCircle,
  Circle,
  XCircle,
  Plus,
  Pencil,
  Mail,
  Webhook,
  Power,
  Tag,
  Waves,
  Heart
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, settingsApi, topicsApi, scheduledBriefingsApi, castsApi, Briefing, ScheduledBriefing } from '../api/client'
import { useStore } from '../store/useStore'
import { formatCompactDate } from '../utils/timezone'
import ScheduledBriefingForm from '../components/ScheduledBriefingForm'

export default function Dashboard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const currentAudio = useStore((s) => s.currentAudio)
  const isPlaying = useStore((s) => s.isPlaying)
  const setCurrentAudio = useStore((s) => s.setCurrentAudio)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  const playAudio = useStore((s) => s.playAudio)
  const togglePlayPause = useStore((s) => s.togglePlayPause)
  
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([])
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(() => {
    const saved = localStorage.getItem('selectedCastId')
    return saved || undefined
  })
  const [showScheduleForm, setShowScheduleForm] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<ScheduledBriefing | null>(null)
  const [listenedFilter, setListenedFilter] = useState<boolean | undefined>(undefined)
  const [filterCastId, setFilterCastId] = useState<string | undefined>(undefined)
  const [filterTopicIds, setFilterTopicIds] = useState<string[]>([])
  const [favoriteFilter, setFavoriteFilter] = useState<boolean | undefined>(undefined)
  const [currentPage, setCurrentPage] = useState(0)
  const [activeTab, setActiveTab] = useState<'audio-briefs' | 'generate' | 'schedules'>('audio-briefs')
  const [isMobile, setIsMobile] = useState(false)
  const pageSize = 10
  
  // Detect mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 640) // sm breakpoint
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])
  
  // Scheduled briefings accordion state - persisted to localStorage
  const [scheduledExpanded] = useState(() => {
    const saved = localStorage.getItem('scheduledBriefingsExpanded')
    return saved !== null ? JSON.parse(saved) : true
  })
  
  // Filters accordion state - persisted to localStorage
  const [filtersExpanded, setFiltersExpanded] = useState(() => {
    const saved = localStorage.getItem('filtersExpanded')
    return saved !== null ? JSON.parse(saved) : false
  })
  
  // Save accordion states to localStorage
  useEffect(() => {
    localStorage.setItem('scheduledBriefingsExpanded', JSON.stringify(scheduledExpanded))
  }, [scheduledExpanded])
  
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
      // Poll more frequently (2s) when a briefing is in progress, otherwise every 10s
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
  
  // Fetch topics for the topic selector
  const { data: topicsData, isLoading: topicsLoading } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  // Fetch scheduled briefings
  const { data: scheduledData, isLoading: scheduledLoading } = useQuery({
    queryKey: ['scheduled-briefings'],
    queryFn: () => scheduledBriefingsApi.list(),
  })
  
  // Fetch casts
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  const topics = topicsData?.topics || []
  const scheduledBriefings = scheduledData?.scheduled_briefings || []
  // Use customer's timezone from settings for all displays
  const timezone = settings?.timezone || 'UTC'
  
  // Check if there's a briefing currently in progress
  const briefingInProgress = data?.briefings.find(
    (b) => b.status === 'pending' || b.status === 'generating'
  )
  
  // Track previously in-progress briefings to detect completion
  const prevInProgressIdsRef = useRef<Set<string>>(new Set())
  // Track which briefings we've already auto-played to prevent duplicate plays
  const autoPlayedBriefingsRef = useRef<Set<string>>(new Set())
  
  // Find the most recently completed briefing (one that was in progress but is now completed)
  const newlyCompletedBriefing = useMemo(() => {
    if (!data?.briefings) return null
    
    const currentInProgressIds = new Set(
      data.briefings
        .filter((b) => b.status === 'pending' || b.status === 'generating')
        .map((b) => b.id)
    )
    
    // Find briefings that were in progress but are now completed
    const completedIds = prevInProgressIdsRef.current
    const newlyCompleted = data.briefings.find(
      (b) => b.status === 'completed' && 
             completedIds.has(b.id) && 
             !currentInProgressIds.has(b.id) &&
             b.audio_url // Make sure it has audio
    )
    
    // Update the ref for next time
    prevInProgressIdsRef.current = currentInProgressIds
    
    return newlyCompleted || null
  }, [data?.briefings])
  
  // Handle starting playback and navigating to detail page
  const handlePlayAndNavigate = (briefing: Briefing) => {
    if (!briefing.audio_url) return
    
    // Start playing using playAudio for mobile compatibility
    // playAudio calls audio.play() synchronously in the click handler
    playAudio({
      id: briefing.id,
      type: 'briefing',
      title: briefing.title,
      audioUrl: briefing.audio_url,
      transcript: briefing.transcript,
      chapters: briefing.chapters,
      initialPosition: briefing.playback_position || undefined,
    })
    
    // Navigate to detail page
    navigate(`/briefing/${briefing.id}`)
  }
  
  // Auto-play when a briefing finishes generating
  // Note: On mobile, this may not auto-play due to browser restrictions on audio
  // without direct user interaction. The user will need to tap play manually.
  useEffect(() => {
    if (newlyCompletedBriefing && newlyCompletedBriefing.audio_url) {
      // Only auto-play if we haven't already played this briefing
      if (!autoPlayedBriefingsRef.current.has(newlyCompletedBriefing.id)) {
        // Mark as auto-played
        autoPlayedBriefingsRef.current.add(newlyCompletedBriefing.id)
        
        // Set up audio (may not auto-play on mobile without user interaction)
        setCurrentAudio({
          id: newlyCompletedBriefing.id,
          type: 'briefing',
          title: newlyCompletedBriefing.title,
          audioUrl: newlyCompletedBriefing.audio_url,
          transcript: newlyCompletedBriefing.transcript,
          chapters: newlyCompletedBriefing.chapters,
          initialPosition: newlyCompletedBriefing.playback_position || undefined,
        })
        setIsPlaying(true)
        
        // Navigate to detail page
        navigate(`/briefing/${newlyCompletedBriefing.id}`)
      }
    }
  }, [newlyCompletedBriefing, setCurrentAudio, setIsPlaying, navigate])
  
  const generateMutation = useMutation({
    mutationFn: (options?: { topicIds?: string[]; castId?: string }) => briefingsApi.generate({ 
      topic_ids: options?.topicIds && options.topicIds.length > 0 ? options.topicIds : undefined,
      cast_id: options?.castId,
    }),
    onSuccess: () => {
      // Clear the newly completed briefing tracking when starting a new generation
      prevInProgressIdsRef.current = new Set()
      autoPlayedBriefingsRef.current.clear()
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
    onError: (error: Error & { response?: { status: number } }) => {
      // Handle 409 conflict (briefing already in progress)
      if (error.response?.status === 409) {
        // Just refresh the list to show the in-progress briefing
        queryClient.invalidateQueries({ queryKey: ['briefings'] })
      }
    },
  })
  
  const deleteMutation = useMutation({
    mutationFn: (id: string) => briefingsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
  })
  
  const cancelMutation = useMutation({
    mutationFn: (id: string) => briefingsApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
  })
  
  const deleteScheduleMutation = useMutation({
    mutationFn: (id: string) => scheduledBriefingsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
    },
  })
  
  const toggleScheduleMutation = useMutation({
    mutationFn: (id: string) => scheduledBriefingsApi.toggle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
    },
  })
  
  const triggerScheduleMutation = useMutation({
    mutationFn: (id: string) => scheduledBriefingsApi.trigger(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
      queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
    },
  })
  
  const handlePlayPause = (briefing: Briefing, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent navigation when clicking play
    
    if (!briefing.audio_url) return
    
    if (currentAudio?.id === briefing.id) {
      // Toggle play/pause for current audio (uses audio manager for mobile compatibility)
      togglePlayPause()
    } else {
      // Start playing this briefing using playAudio for mobile compatibility
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
  
  const truncateTranscript = (transcript?: string, maxLength = 150) => {
    if (!transcript) return null
    // Remove HOST1:/HOST2: prefixes for preview
    const cleaned = transcript.replace(/HOST[12]:\s*/gi, '').trim()
    if (cleaned.length <= maxLength) return cleaned
    return cleaned.substring(0, maxLength).trim() + '...'
  }
  
  const handleGenerate = () => {
    generateMutation.mutate({
      topicIds: selectedTopicIds.length > 0 ? selectedTopicIds : undefined,
      castId: selectedCastId,
    })
  }
  
  const casts = castsData?.casts || []
  const defaultCast = casts.find(c => c.is_default)
  
  // Persist selectedCastId to localStorage
  useEffect(() => {
    if (selectedCastId) {
      localStorage.setItem('selectedCastId', selectedCastId)
    }
  }, [selectedCastId])
  
  // Initialize selectedCastId with default cast when casts are loaded (only if not already set)
  useEffect(() => {
    if (defaultCast && selectedCastId === undefined) {
      setSelectedCastId(defaultCast.id)
    }
  }, [defaultCast, selectedCastId])
  
  // Validate that selectedCastId still exists in casts list (in case cast was deleted)
  useEffect(() => {
    if (casts.length > 0 && selectedCastId) {
      const castExists = casts.some(c => c.id === selectedCastId)
      if (!castExists) {
        // Cast was deleted, fall back to default
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
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    
    // Get dates in user's timezone for comparison
    const dateInTz = new Date(dateStr)
    const nowInTz = new Date()
    
    // Format time in user's timezone with minutes for precision
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
    
    // Same day - always show the actual time for precision
    if (dateStrInTz === nowStrInTz) {
      const timeStr = timeFormatter.format(dateInTz)
      // For very recent items (less than 1 minute), show both relative and time
      if (diffMins < 1) {
        return `Just now (${timeStr})`
      }
      // For items less than 1 hour, show both minutes and time
      if (diffMins < 60) {
        return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago (${timeStr})`
      }
      // For same day but more than an hour, show "at 8:15am today"
      return `at ${timeStr} today`
    }
    
    // Yesterday
    const yesterday = new Date(nowInTz)
    yesterday.setDate(yesterday.getDate() - 1)
    const yesterdayStr = dateFormatter.format(yesterday)
    if (dateStrInTz === yesterdayStr) {
      const timeStr = timeFormatter.format(dateInTz)
      return `at ${timeStr} yesterday`
    }
    
    // Older than yesterday - show date and time
    const timeStr = timeFormatter.format(dateInTz)
    return `${dateFormatter.format(dateInTz)} at ${timeStr}`
  }
  
  // Prepare animation items for the generation progress
  const animationItems = useMemo(() => {
    if (!briefingInProgress) return []
    
    const items: Array<{ type: 'topic' | 'source' | 'article' | 'step'; text: string }> = []
    
    // Add selected topics
    const selectedTopics = topics.filter(t => selectedTopicIds.includes(t.id))
    selectedTopics.forEach(topic => {
      items.push({ type: 'topic', text: topic.name })
    })
    
    // Add sources from briefing if available
    if (briefingInProgress.sources && briefingInProgress.sources.length > 0) {
      briefingInProgress.sources.slice(0, 5).forEach(source => {
        items.push({ type: 'source', text: source.title })
      })
    }
    
    // Add generic generation steps
    items.push({ type: 'step', text: 'Gathering news articles...' })
    items.push({ type: 'step', text: 'Analyzing stories...' })
    items.push({ type: 'step', text: 'Writing script...' })
    items.push({ type: 'step', text: 'Generating audio...' })
    
    return items
  }, [briefingInProgress, topics, selectedTopicIds])
  
  // Animated item component
  const AnimatedGenerationItem = ({ items }: { items: Array<{ type: string; text: string }> }) => {
    const [currentIndex, setCurrentIndex] = useState(0)
    const [fadeState, setFadeState] = useState<'in' | 'out'>('in')
    const intervalRef = useRef<number | null>(null)
    const timeoutRef = useRef<number | null>(null)
    const itemsRef = useRef(items)
    const isInitializedRef = useRef(false)
    
    // Update items ref without restarting animation
    useEffect(() => {
      itemsRef.current = items
      // Ensure current index is valid if items changed
      if (items.length > 0 && currentIndex >= items.length) {
        setCurrentIndex(0)
      }
    }, [items, currentIndex])
    
    useEffect(() => {
      if (items.length === 0) {
        // Clear any existing intervals
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current)
          timeoutRef.current = null
        }
        isInitializedRef.current = false
        return
      }
      
      // Only initialize animation once - never restart it
      if (!isInitializedRef.current) {
        isInitializedRef.current = true
        // Start with fade in
        setFadeState('in')
        
        intervalRef.current = setInterval(() => {
          // Fade out
          setFadeState('out')
          
          // After fade out completes, change item and fade in
          timeoutRef.current = setTimeout(() => {
            setCurrentIndex((prev) => {
              const currentItems = itemsRef.current
              if (currentItems.length === 0) return 0
              return (prev + 1) % currentItems.length
            })
            setFadeState('in')
          }, 500) // Wait for fade out animation to complete
        }, 2500) // Change every 2.5 seconds (2s visible + 0.5s fade)
      }
    }, []) // Empty deps - only run once on mount
    
    // Cleanup on unmount
    useEffect(() => {
      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current)
          timeoutRef.current = null
        }
        isInitializedRef.current = false
      }
    }, [])
    
    if (items.length === 0) return null
    
    // Ensure index is valid
    const safeIndex = currentIndex >= items.length ? 0 : currentIndex
    const currentItem = items[safeIndex]
    
    return (
      <div className="relative h-8 sm:h-10 flex items-center overflow-hidden">
        <div
          key={`${safeIndex}-${currentItem.text}`}
          className={clsx(
            'absolute inset-0 flex items-center gap-2 transition-opacity duration-500 ease-in-out',
            fadeState === 'in' ? 'opacity-100' : 'opacity-0'
          )}
        >
          {currentItem.type === 'topic' && <Tag className="w-4 h-4 text-augustus-400 flex-shrink-0" />}
          {currentItem.type === 'source' && <FileText className="w-4 h-4 text-augustus-400 flex-shrink-0" />}
          {(currentItem.type === 'article' || currentItem.type === 'step') && <Sparkles className="w-4 h-4 text-yellow-400 flex-shrink-0" />}
          <span className="text-xs sm:text-sm text-augustus-300 truncate">
            {currentItem.text}
          </span>
        </div>
      </div>
    )
  }

  // Helper function to render a briefing card
  const renderBriefingCard = (briefing: Briefing, isLatest: boolean, isCurrentlyPlaying: boolean, briefingTopics: typeof topics) => {
    if (isLatest) {
      return (
        <div
          key={briefing.id}
          onClick={() => navigate(`/briefing/${briefing.id}`)}
          className="relative group cursor-pointer overflow-hidden rounded-[2rem] bg-augustus-900 border border-augustus-800/50 shadow-2xl transition-all hover:border-augustus-700 active:scale-[0.99] min-h-[380px] sm:min-h-[450px] flex flex-col p-6 sm:p-10"
        >
          {/* Subtle Background Pattern/Gradient */}
          <div className="absolute inset-0 bg-gradient-to-br from-accent/10 via-transparent to-transparent opacity-50" />
          <div className="absolute -right-20 -top-20 w-96 h-96 bg-accent/25 rounded-full blur-[100px] animate-spotlight pointer-events-none" />
          
          {/* Chapter Names Background */}
          {briefing.chapters && briefing.chapters.length > 0 && (
            <div className="absolute inset-0 overflow-visible pointer-events-none">
              <div
                className="absolute font-black text-white uppercase tracking-tighter opacity-5 text-8xl sm:text-[12rem] top-1/2 -translate-y-1/2 left-0 -translate-x-8 w-[150%] text-left leading-[0.9]"
                style={{ 
                  textShadow: '0 0 20px rgba(255,255,255,0.1)'
                }}
              >
                {briefing.chapters.map(c => c.title).join(' ')}
              </div>
            </div>
          )}
          
          {/* Content Container */}
          <div className="relative z-10 flex flex-col h-full justify-between flex-1">
            {/* Top Row: Cast & Status */}
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
              
              {/* Delete Button */}
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

            {/* Middle: Topics & Title */}
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
              
              {/* Progress bar for generating briefings */}
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

            {/* Bottom: Date • Duration • Summary */}
            {briefing.status === 'completed' && briefing.extra_data?.story_analysis ? (
              <div className="mt-auto flex flex-col sm:flex-row sm:items-end justify-between gap-6 sm:gap-8">
                <div className="flex-1">
                  <p className="text-base sm:text-lg text-augustus-300 leading-relaxed">
                    <span className="text-augustus-400">
                      {formatDateShort(briefing.created_at)} • {formatDurationLong(briefing.duration_seconds)} • 
                    </span>{' '}
                    <span className="text-augustus-200">
                      {(() => {
                        const summary = (briefing.extra_data?.story_analysis as string) || ''
                        const maxLength = 300
                        return summary.length > maxLength ? summary.substring(0, maxLength).trim() + '...' : summary
                      })()}
                    </span>
                  </p>
                </div>
                
                {/* Prominent Play Button */}
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
                  {briefing.status === 'generating' || briefing.status === 'pending' ? (
                    <Loader2 className="w-10 h-10 animate-spin" />
                  ) : isCurrentlyPlaying ? (
                    <Pause className="w-10 h-10 sm:w-14 sm:h-14 fill-current relative z-10" />
                  ) : (
                    <Play className="w-10 h-10 sm:w-14 sm:h-14 fill-current ml-1.5 relative z-10" />
                  )}
                </button>
              </div>
            ) : (
              <div className="mt-auto flex flex-col sm:flex-row sm:items-end justify-between gap-8">
                {/* Large Stats */}
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
                        {new Date(briefing.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                    <span className="text-[9px] uppercase tracking-[0.2em] text-augustus-500 font-black mt-3">Released</span>
                  </div>
                </div>

                {/* Prominent Play Button */}
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
         {/* Delete Button - show for errors */}
         {briefing.error_message && (
           <button
             onClick={(e) => {
               e.stopPropagation()
               if (confirm('Are you sure you want to delete this briefing?')) {
                 deleteMutation.mutate(briefing.id)
               }
             }}
             className="absolute top-4 right-4 btn btn-ghost p-2 text-augustus-500 hover:text-red-400 flex-shrink-0 z-10"
             title="Delete"
           >
             <Trash2 className="w-4 h-4 sm:w-5 sm:h-5" />
           </button>
         )}
         
         <div className={clsx(
           'flex flex-col',
           briefing.status === 'completed' && 'pl-14 sm:pl-16'
         )}>
           {/* Topics */}
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
          
          {/* Title */}
          <h3 className={clsx(
            'font-semibold text-white truncate group-hover:text-accent transition-colors mb-2',
            isLatest ? 'text-lg sm:text-2xl' : 'text-sm sm:text-base'
          )}>
            {briefing.title}
          </h3>
          
          {/* Date • Duration • Summary preview format */}
          {briefing.status === 'completed' && briefing.extra_data?.story_analysis ? (
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
                    const summary = (briefing.extra_data?.story_analysis as string) || ''
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
          
          {/* Progress bar for generating briefings */}
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
        
         {/* Play button - positioned absolutely or as overlay */}
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
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          Dashboard
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          AI-generated audio briefings from your news feeds
        </p>
      </div>
      
      {/* Tab Navigation */}
      <div className="mb-6 sm:mb-8">
        <div className="inline-flex bg-augustus-800/50 p-1 rounded-full">
          <button
            onClick={() => setActiveTab('audio-briefs')}
            className={clsx(
              'px-4 sm:px-6 py-2 sm:py-2.5 rounded-full text-sm sm:text-base font-medium transition-all',
              activeTab === 'audio-briefs'
                ? 'bg-accent text-white'
                : 'text-augustus-300 hover:text-white'
            )}
          >
            Briefs
          </button>
          <button
            onClick={() => setActiveTab('generate')}
            className={clsx(
              'px-4 sm:px-6 py-2 sm:py-2.5 rounded-full text-sm sm:text-base font-medium transition-all',
              activeTab === 'generate'
                ? 'bg-accent text-white'
                : 'text-augustus-300 hover:text-white'
            )}
          >
            Generate
          </button>
          <button
            onClick={() => setActiveTab('schedules')}
            className={clsx(
              'px-4 sm:px-6 py-2 sm:py-2.5 rounded-full text-sm sm:text-base font-medium transition-all',
              activeTab === 'schedules'
                ? 'bg-accent text-white'
                : 'text-augustus-300 hover:text-white'
            )}
          >
            Schedules
          </button>
        </div>
      </div>
      
      {/* Tab Content */}
      {activeTab === 'generate' && (
        <>
          {/* Generate new briefing */}
      <div className="card mb-6 sm:mb-8">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-accent" />
          Generate New Briefing
        </h2>
        
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-accent text-white text-xs font-semibold flex-shrink-0">1</span>
            <p className="text-xs sm:text-sm text-augustus-400">Select topics to include:</p>
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
                    'px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 min-h-[36px]',
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
              <button
                onClick={() => navigate('/topics')}
                className="px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 min-h-[36px] bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600 border border-augustus-700 hover:border-augustus-600"
              >
                <Plus className="w-3.5 h-3.5" />
                Create Topic
              </button>
            </div>
          )}
          {selectedTopicIds.length === 0 && topics.length > 0 && (
            <p className="text-xs text-augustus-500 mt-2">
              No topics selected - all topics will be included
            </p>
          )}
        </div>
        
        {/* Cast selector */}
        {casts.length > 1 && (
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-accent text-white text-xs font-semibold flex-shrink-0">2</span>
              <label className="text-xs sm:text-sm text-augustus-400">
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
        
        {/* Show newly completed briefing button */}
        {newlyCompletedBriefing && !briefingInProgress && activeTab === 'generate' && (
          <div className="mb-4 sm:mb-6 p-4 sm:p-5 bg-green-500/10 border border-green-500/20 rounded-lg">
            <div className="flex items-start gap-3 sm:gap-4">
              <CheckCircle className="w-5 h-5 sm:w-6 sm:h-6 text-green-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-green-400 font-medium text-sm sm:text-base mb-1">
                  Briefing ready!
                </p>
                <p className="text-xs sm:text-sm text-augustus-400 mb-3 sm:mb-4 truncate">
                  {newlyCompletedBriefing.title}
                </p>
                <button
                  onClick={() => handlePlayAndNavigate(newlyCompletedBriefing)}
                  className="btn btn-primary flex items-center justify-center gap-2 w-full sm:w-auto"
                >
                  <Play className="w-4 h-4 sm:w-5 sm:h-5" />
                  Play & View Details
                </button>
              </div>
            </div>
          </div>
        )}
        
        {/* Show in-progress message or generate button */}
        {briefingInProgress ? (
          <div className="p-3 sm:p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
            <div className="flex items-start justify-between gap-3 sm:gap-4">
              <div className="flex items-start gap-2 sm:gap-3 flex-1 min-w-0">
                <Loader2 className="w-5 h-5 animate-spin text-yellow-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-yellow-400 font-medium text-sm sm:text-base">Generating briefing...</p>
                  <p className="text-xs sm:text-sm text-augustus-400 mb-2 sm:mb-3 truncate">
                    {briefingInProgress.title}
                  </p>
                  
                  {/* Animated sources/articles */}
                  {animationItems.length > 0 && (
                    <div className="mb-2 sm:mb-3">
                      <AnimatedGenerationItem items={animationItems} />
                    </div>
                  )}
                  
                  {/* Progress bar */}
                  {briefingInProgress.extra_data?.progress && (
                    <div className="space-y-1 sm:space-y-2">
                      <div className="flex justify-between text-xs">
                        <span className="text-augustus-400 truncate mr-2">
                          Step {briefingInProgress.extra_data.progress.step}/{briefingInProgress.extra_data.progress.total_steps}: {briefingInProgress.extra_data.progress.step_name}
                        </span>
                        <span className="text-augustus-500 flex-shrink-0">
                          {briefingInProgress.extra_data.progress.percent}%
                        </span>
                      </div>
                      <div className="h-2 bg-augustus-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-yellow-500 rounded-full transition-all duration-500"
                          style={{ width: `${briefingInProgress.extra_data.progress.percent}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              {/* Cancel button */}
              <button
                onClick={() => cancelMutation.mutate(briefingInProgress.id)}
                disabled={cancelMutation.isPending}
                className="btn btn-ghost p-2 text-augustus-400 hover:text-red-400 hover:bg-red-500/10 flex-shrink-0"
                title="Cancel briefing"
              >
                {cancelMutation.isPending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <XCircle className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-accent text-white text-xs font-semibold flex-shrink-0">{casts.length > 1 ? '3' : '2'}</span>
              <p className="text-xs sm:text-sm text-augustus-400">Generate your briefing:</p>
            </div>
            <button
              onClick={handleGenerate}
              disabled={generateMutation.isPending}
              className="btn btn-primary flex items-center justify-center gap-2"
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  Create Briefing Now
                </>
              )}
            </button>
          </div>
        )}
      </div>
        </>
      )}
      
      {activeTab === 'schedules' && (
        <>
          {/* Scheduled Briefings Section */}
          <div className="card mb-6 sm:mb-8">
            <div className="flex items-center justify-between gap-2 mb-4">
              <h2 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
                <Calendar className="w-5 h-5 text-accent" />
                Scheduled Briefings
                {scheduledBriefings.length > 0 && (
                  <span className="text-xs sm:text-sm font-normal text-augustus-500">
                    ({scheduledBriefings.length})
                  </span>
                )}
              </h2>
              <button
                onClick={() => {
                  setEditingSchedule(null)
                  setShowScheduleForm(true)
                }}
                className="btn btn-primary flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                <span className="hidden sm:inline">New Schedule</span>
              </button>
            </div>
            
            {scheduledLoading ? (
              <div className="flex items-center justify-center py-6 sm:py-8">
                <Loader2 className="w-6 h-6 animate-spin text-accent" />
              </div>
            ) : scheduledBriefings.length === 0 ? (
              <div className="text-center py-6 sm:py-8">
                <Calendar className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
                <p className="text-sm sm:text-base text-augustus-400 mb-1">No scheduled briefings yet.</p>
                <p className="text-xs sm:text-sm text-augustus-500 mb-4">Set up automatic briefings to be generated at specific times.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {scheduledBriefings.map((schedule) => {
                  const daysLabels = schedule.schedule_days
                    .sort()
                    .map((d) => {
                      const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                      return dayNames[d]
                    })
                    .join(', ')
                  
                  return (
                    <div
                      key={schedule.id}
                      className="p-3 sm:p-4 bg-augustus-900 rounded-lg border border-augustus-800 hover:border-augustus-700 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3 sm:gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1.5 sm:mb-2 flex-wrap">
                            <h3 className="font-semibold text-white text-sm sm:text-base">{schedule.name}</h3>
                            <span
                              className={clsx(
                                'px-2 py-0.5 rounded-full text-xs font-medium',
                                schedule.is_active
                                  ? 'bg-green-500/20 text-green-400'
                                  : 'bg-augustus-700 text-augustus-500'
                              )}
                            >
                              {schedule.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </div>
                          <div className="flex flex-wrap items-center gap-x-3 sm:gap-x-4 gap-y-1 text-xs sm:text-sm text-augustus-400">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                              {schedule.schedule_time}
                            </span>
                            <span>{daysLabels}</span>
                            <span className="flex items-center gap-1">
                              {schedule.notification_methods.length > 0 ? (
                                <>
                                  {schedule.notification_methods.includes('email') && (
                                    <Mail className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                                  )}
                                  {schedule.notification_methods.includes('webhook') && (
                                    <Webhook className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                                  )}
                                </>
                              ) : (
                                <span className="text-augustus-500 text-xs">Dashboard only</span>
                              )}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => {
                              setEditingSchedule(schedule)
                              setShowScheduleForm(true)
                            }}
                            className="btn btn-ghost p-2 text-augustus-500 hover:text-accent"
                            title="Edit"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => toggleScheduleMutation.mutate(schedule.id)}
                            disabled={toggleScheduleMutation.isPending}
                            className={clsx(
                              'btn btn-ghost p-2',
                              schedule.is_active
                                ? 'text-augustus-500 hover:text-yellow-400'
                                : 'text-augustus-500 hover:text-green-400'
                            )}
                            title={schedule.is_active ? 'Disable' : 'Enable'}
                          >
                            {toggleScheduleMutation.isPending ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Power className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={() => {
                              if (confirm('Are you sure you want to delete this schedule?')) {
                                deleteScheduleMutation.mutate(schedule.id)
                              }
                            }}
                            className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                      
                      {/* Manual Trigger Button */}
                      <div className="mt-3 pt-3 border-t border-augustus-800/50">
                        <button
                          onClick={() => triggerScheduleMutation.mutate(schedule.id)}
                          disabled={triggerScheduleMutation.isPending || !schedule.is_active}
                          className={clsx(
                            'btn btn-primary flex items-center justify-center gap-2 w-full sm:w-auto',
                            !schedule.is_active && 'opacity-50 cursor-not-allowed'
                          )}
                        >
                          {triggerScheduleMutation.isPending ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              Generating...
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-4 h-4" />
                              Generate Now
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
      
      {activeTab === 'audio-briefs' && (
        <>
          {/* Briefings list */}
          <div className="space-y-3 sm:space-y-4">
        {/* Filter controls */}
        <div className="card mb-6 sm:mb-8">
          {/* Filters Accordion Header */}
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
          
          {/* Filters Accordion Content */}
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
                    {casts.map((cast) => (
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
                    {topics.map((topic) => (
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
              
              {/* Clear filters button - show on mobile when filters are active */}
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
            // Group briefings by listened status (only when showing all, not when filtered)
            const shouldGroupByListened = listenedFilter === undefined
            const briefings = data?.briefings || []
            
            if (shouldGroupByListened) {
              // Split into not listened and listened groups
              const notListened = briefings.filter(b => !b.listened)
              const listened = briefings.filter(b => b.listened)
              
              return (
                <>
                  {/* Not Listened Section */}
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
                      {notListened.map((briefing, index) => {
                        const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
                        const isLatest = isMobile && notListened.length > 0
                        // Get topic IDs from extra_data
                        const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
                        // Match with topics data
                        const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
                        
                        return renderBriefingCard(briefing, isLatest, isCurrentlyPlaying, briefingTopics)
                      })}
                    </>
                  )}
                  
                  {/* Listened Section */}
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
                      {listened.map((briefing, index) => {
                        const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
                        const isLatest = false // Only show latest styling for first not-listened item
                        // Get topic IDs from extra_data
                        const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
                        // Match with topics data
                        const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
                        
                        return renderBriefingCard(briefing, isLatest, isCurrentlyPlaying, briefingTopics)
                      })}
                    </>
                  )}
                </>
              )
            } else {
              // No grouping when filter is applied - show all briefings normally
              return briefings.map((briefing, index) => {
                const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
                const isLatest = isMobile && !briefing.listened
                // Get topic IDs from extra_data
                const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
                // Match with topics data
                const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
                
                return renderBriefingCard(briefing, isLatest, isCurrentlyPlaying, briefingTopics)
              })
            }
          })()
        )}
        
        {/* Pagination footer - simplified on mobile */}
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
        </>
      )}
      
      {/* Scheduled Briefing Form Modal */}
      <ScheduledBriefingForm
        isOpen={showScheduleForm}
        onClose={() => {
          setShowScheduleForm(false)
          setEditingSchedule(null)
        }}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
        }}
        initialTopicIds={selectedTopicIds.length > 0 ? selectedTopicIds : undefined}
        initialCastId={selectedCastId}
        editingSchedule={editingSchedule}
      />
    </div>
  )
}
