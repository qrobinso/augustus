import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import { 
  ArrowLeft, 
  Play, 
  Pause,
  Clock, 
  Calendar,
  Loader2,
  AlertCircle,
  FileText,
  ExternalLink,
  Volume2,
  CheckCircle,
  Circle,
  Copy,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Cpu,
  FileAudio,
  Zap,
  BarChart3,
  Heart,
  Trash2,
  CalendarClock,
  Download,
  Navigation2
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, settingsApi, castsApi, scheduledBriefingsApi, topicsApi, SegmentTiming } from '../api/client'
import { useStore } from '../store/useStore'
import { formatFullDate } from '../utils/timezone'
import { audioManager } from '../utils/audioManager'

export default function BriefingDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const segmentRefs = useRef<Map<number, HTMLDivElement>>(new Map())
  const transcriptContainerRef = useRef<HTMLDivElement | null>(null)
  const isAutoScrollingRef = useRef(false)
  const shouldAutoScrollRef = useRef(true)
  
  const currentAudio = useStore((s) => s.currentAudio)
  const isPlaying = useStore((s) => s.isPlaying)
  const setCurrentAudio = useStore((s) => s.setCurrentAudio)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  const playAudio = useStore((s) => s.playAudio)
  const togglePlayPause = useStore((s) => s.togglePlayPause)
  
  // Track active segment for highlighting
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null)
  const [hasAutoPlayed, setHasAutoPlayed] = useState(false)
  const [notesExpanded, setNotesExpanded] = useState(false)
  const [nerdStatsExpanded, setNerdStatsExpanded] = useState(false)
  const [audioFileSize, setAudioFileSize] = useState<number | null>(null)
  const [showCreateScheduleModal, setShowCreateScheduleModal] = useState(false)
  const [showScrollToTranscript, setShowScrollToTranscript] = useState(false)
  
  const { data: briefing, isLoading, error } = useQuery({
    queryKey: ['briefing', id],
    queryFn: () => briefingsApi.get(id!),
    enabled: !!id,
  })
  
  // Fetch settings for timezone
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })
  
  const timezone = settings?.timezone || 'UTC'
  
  // Fetch topics for schedule name
  const { data: topicsData } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  const topics = topicsData?.topics || []
  
  // Fetch cast information if cast_id exists (always fetch to get actual names)
  const { data: cast } = useQuery({
    queryKey: ['cast', briefing?.cast_id],
    queryFn: () => castsApi.get(briefing!.cast_id!),
    enabled: !!briefing?.cast_id,
  })
  
  // Fallback: fetch all casts to get the default one if no cast_id on the briefing
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
    enabled: !!briefing && !briefing.cast_id && !briefing.extra_data?.cast_member_names,
  })
  
  // Use the specific cast, or fall back to the default cast
  const effectiveCast = cast || castsData?.casts?.find(c => c.is_default)
  
  // Mutation for updating listened status
  const listenedMutation = useMutation({
    mutationFn: ({ listened }: { listened: boolean }) => 
      briefingsApi.updateListened(id!, listened),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing', id] })
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
  })
  
  // Mutation for updating favorite status
  const favoriteMutation = useMutation({
    mutationFn: ({ favorite }: { favorite: boolean }) => 
      briefingsApi.updateFavorite(id!, favorite),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing', id] })
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
  })
  
  // Mutation for deleting briefing
  const deleteMutation = useMutation({
    mutationFn: () => briefingsApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
      navigate('/dashboard')
    },
  })
  
  // Mutation for creating schedule from briefing
  const createScheduleMutation = useMutation({
    mutationFn: (options: {
      schedule_time: string
      schedule_days: number[]
    }) => {
      const topicIds = (briefing?.extra_data?.topic_ids as string[]) || []
      const maxDurationMinutes = briefing?.duration_seconds 
        ? Math.ceil(briefing.duration_seconds / 60)
        : 5
      
      // Create schedule name from topic names
      const topicNames = topicIds
        .map(id => topics.find(t => t.id === id)?.name)
        .filter(Boolean) as string[]
      
      const scheduleName = topicNames.length > 0
        ? topicNames.join(', ')
        : briefing?.title || 'Daily Briefing'
      
      return scheduledBriefingsApi.create({
        name: scheduleName,
        topic_ids: topicIds,
        schedule_time: options.schedule_time,
        schedule_days: options.schedule_days,
        notification_methods: [],
        is_active: true,
        max_duration_minutes: maxDurationMinutes,
        cast_id: briefing?.cast_id,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
      setShowCreateScheduleModal(false)
    },
  })
  
  const isCurrentlyPlaying = currentAudio?.id === id && isPlaying
  const isThisBriefingLoaded = currentAudio?.id === id
  
  // Get segment timings from extra_data
  const segmentTimings: SegmentTiming[] = briefing?.extra_data?.segment_timings || []
  
  // Get chapters from briefing
  const chapters = briefing?.chapters || []
  
  // Debug: log chapters to console
  useEffect(() => {
    if (briefing) {
      console.log('[BriefingDetail] Briefing chapters:', chapters)
      console.log('[BriefingDetail] Briefing extra_data:', briefing.extra_data)
    }
  }, [briefing, chapters])

  // Fetch audio file size
  useEffect(() => {
    if (briefing?.audio_url) {
      const fetchFileSize = async () => {
        try {
          const response = await fetch(briefing.audio_url!, { method: 'HEAD' })
          const contentLength = response.headers.get('content-length')
          if (contentLength) {
            setAudioFileSize(parseInt(contentLength, 10))
          }
        } catch (error) {
          console.error('Failed to fetch audio file size:', error)
        }
      }
      fetchFileSize()
    } else {
      setAudioFileSize(null)
    }
  }, [briefing?.audio_url])

  // Format file size helper
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }
  
  // Get cast member names mapping from extra_data (HOST1 -> name, HOST2 -> name, etc.)
  const castMemberNamesFromExtraData = briefing?.extra_data?.cast_member_names as Record<string, string> | undefined
  
  // Build cast member names mapping from cast data if not in extra_data
  // Use useMemo to ensure it updates reactively when cast data loads
  const castMemberNames = useMemo(() => {
    if (castMemberNamesFromExtraData) {
      return castMemberNamesFromExtraData
    }
    if (effectiveCast && effectiveCast.members && effectiveCast.members.length > 0) {
      const mapping: Record<string, string> = {}
      const sortedMembers = [...effectiveCast.members].sort((a, b) => a.order - b.order)
      sortedMembers.forEach((member, index) => {
        mapping[`HOST${index + 1}`] = member.name
      })
      return mapping
    }
    return undefined
  }, [castMemberNamesFromExtraData, effectiveCast])
  
  // Helper function to get cast member name for a speaker
  const getCastMemberName = useCallback((speaker: string): string => {
    const speakerUpper = speaker.toUpperCase()
    
    // First try the mapping from extra_data or cast
    if (castMemberNames && castMemberNames[speakerUpper]) {
      return castMemberNames[speakerUpper]
    }
    
    // If we have cast data but mapping not built yet (shouldn't happen, but just in case)
    if (effectiveCast && effectiveCast.members && effectiveCast.members.length > 0) {
      const hostMatch = speakerUpper.match(/^HOST(\d+)$/)
      if (hostMatch) {
        const hostNum = parseInt(hostMatch[1], 10)
        const sortedMembers = [...effectiveCast.members].sort((a, b) => a.order - b.order)
        if (hostNum > 0 && hostNum <= sortedMembers.length) {
          return sortedMembers[hostNum - 1].name
        }
      }
    }
    
    // Final fallback: return the speaker identifier as-is (should rarely happen)
    return speakerUpper
  }, [castMemberNames, effectiveCast])
  
  // Find the active segment based on current time
  const findActiveSegment = useCallback((time: number): number | null => {
    for (let i = 0; i < segmentTimings.length; i++) {
      const segment = segmentTimings[i]
      if (time >= segment.start_seconds && time < segment.end_seconds) {
        return i
      }
    }
    // If past all segments, return last one
    if (segmentTimings.length > 0 && time >= segmentTimings[segmentTimings.length - 1].start_seconds) {
      return segmentTimings.length - 1
    }
    return null
  }, [segmentTimings])
  
  // Set up audio time tracking using audioManager
  useEffect(() => {
    if (!isThisBriefingLoaded || currentAudio?.id !== id) {
      setActiveSegmentIndex(null)
      return
    }
    
    // Update time handler
    const handleTimeUpdate = (time: number) => {
      const newActiveIndex = findActiveSegment(time)
      setActiveSegmentIndex(newActiveIndex)
    }
    
    // Initial check
    const initialTime = audioManager.currentTime
    handleTimeUpdate(initialTime)
    
    // Subscribe to time updates from audioManager
    const unsubscribe = audioManager.onTimeUpdate(handleTimeUpdate)
    
    return () => {
      unsubscribe()
    }
  }, [isThisBriefingLoaded, currentAudio?.id, id, findActiveSegment])
  
  // Auto-scroll to active segment (only if shouldAutoScrollRef is true)
  useEffect(() => {
    if (activeSegmentIndex !== null && isCurrentlyPlaying && shouldAutoScrollRef.current) {
      const segmentEl = segmentRefs.current.get(activeSegmentIndex)
      if (segmentEl) {
        isAutoScrollingRef.current = true
        segmentEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
        // Reset flag after scroll completes
        setTimeout(() => {
          isAutoScrollingRef.current = false
        }, 500)
      }
    }
  }, [activeSegmentIndex, isCurrentlyPlaying])

  // Check if user has scrolled away from the active segment
  useEffect(() => {
    if (!isCurrentlyPlaying || activeSegmentIndex === null) {
      setShowScrollToTranscript(false)
      shouldAutoScrollRef.current = true
      return
    }

    const checkScrollPosition = () => {
      // Skip if we're currently auto-scrolling
      if (isAutoScrollingRef.current) {
        return
      }

      const segmentEl = segmentRefs.current.get(activeSegmentIndex)
      if (!segmentEl) {
        setShowScrollToTranscript(false)
        shouldAutoScrollRef.current = true
        return
      }

      const segmentRect = segmentEl.getBoundingClientRect()
      const viewportHeight = window.innerHeight
      const viewportCenter = viewportHeight / 2
      
      // Check if the active segment is visible in the viewport
      const isVisible = 
        segmentRect.top >= 0 &&
        segmentRect.bottom <= viewportHeight &&
        segmentRect.left >= 0 &&
        segmentRect.right <= window.innerWidth

      // Also check if it's reasonably close to the viewport center (within 250px)
      const segmentCenter = segmentRect.top + segmentRect.height / 2
      const distanceFromCenter = Math.abs(segmentCenter - viewportCenter)
      const isNearCenter = distanceFromCenter < 250

      const isScrolledAway = !isVisible && !isNearCenter
      
      if (isScrolledAway) {
        // User has scrolled away - stop auto-scrolling and show pill
        shouldAutoScrollRef.current = false
        setShowScrollToTranscript(true)
      } else {
        // User is near the active segment - resume auto-scrolling and hide pill
        shouldAutoScrollRef.current = true
        setShowScrollToTranscript(false)
      }
    }

    // Check on scroll with debouncing
    let scrollTimeout: NodeJS.Timeout
    const handleScroll = () => {
      if (!isAutoScrollingRef.current) {
        clearTimeout(scrollTimeout)
        scrollTimeout = setTimeout(checkScrollPosition, 100)
      }
    }

    // Check when active segment changes
    const checkInterval = setInterval(() => {
      if (!isAutoScrollingRef.current) {
        checkScrollPosition()
      }
    }, 500)

    window.addEventListener('scroll', handleScroll, { passive: true })
    
    // Initial check
    checkScrollPosition()
    
    return () => {
      clearTimeout(scrollTimeout)
      clearInterval(checkInterval)
      window.removeEventListener('scroll', handleScroll)
    }
  }, [activeSegmentIndex, isCurrentlyPlaying])

  // Handle clicking the scroll-to-transcript pill
  const handleScrollToTranscript = () => {
    if (activeSegmentIndex !== null) {
      const segmentEl = segmentRefs.current.get(activeSegmentIndex)
      if (segmentEl) {
        // Resume auto-scrolling
        shouldAutoScrollRef.current = true
        isAutoScrollingRef.current = true
        segmentEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
        setTimeout(() => {
          isAutoScrollingRef.current = false
          setShowScrollToTranscript(false)
        }, 500)
      }
    }
  }
  
  const handlePlayPause = () => {
    if (!briefing?.audio_url) return
    
    if (currentAudio?.id === id) {
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
  
  // Auto-play if autoplay parameter is present in URL
  // Note: On mobile, this may not auto-play due to browser restrictions.
  // The audio will be set up, but user may need to tap play manually.
  useEffect(() => {
    const audioUrl = briefing?.audio_url
    if (audioUrl && briefing.status === 'completed' && !hasAutoPlayed && id) {
      const shouldAutoplay = searchParams.get('autoplay') === 'true'
      if (shouldAutoplay) {
        // Small delay to ensure audio element is ready
        const timer = setTimeout(() => {
          if (currentAudio?.id === id) {
            // Toggle play/pause for current audio
            setIsPlaying(!isPlaying)
          } else {
            // Set up audio (may not auto-play on mobile without direct user interaction)
            setCurrentAudio({
              id: briefing.id,
              type: 'briefing',
              title: briefing.title,
              audioUrl: audioUrl,
              transcript: briefing.transcript,
              chapters: briefing.chapters,
              initialPosition: briefing.playback_position || undefined,
            })
            setIsPlaying(true)
          }
          setHasAutoPlayed(true)
          // Remove autoplay parameter from URL without reload
          navigate(`/briefing/${id}`, { replace: true })
        }, 500)
        return () => clearTimeout(timer)
      }
    }
  }, [briefing, searchParams, hasAutoPlayed, id, navigate, currentAudio, isPlaying, setCurrentAudio, setIsPlaying])
  
  const handleSeekToSegment = (startSeconds: number) => {
    // First, ensure the audio is loaded
    if (!briefing?.audio_url) return
    
    // If not currently playing this briefing, start it first
    if (currentAudio?.id !== id) {
      // Use playAudio for mobile compatibility - starts playing from the segment position
      playAudio({
        id: briefing.id,
        type: 'briefing',
        title: briefing.title,
        audioUrl: briefing.audio_url,
        transcript: briefing.transcript,
        chapters: briefing.chapters,
        initialPosition: startSeconds,  // Use the segment start as initial position
      })
    } else {
      // Already playing this briefing, just seek using audio manager
      audioManager.seek(startSeconds)
      if (!isPlaying) {
        togglePlayPause()
      }
    }
  }
  
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--:--'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }
  
  const formatDate = (dateStr: string) => {
    return formatFullDate(dateStr, timezone)
  }
  
  // Get transcript as plain text for copying
  const getTranscriptText = () => {
    // If we have segment timings, format them as text
    if (segmentTimings.length > 0) {
      return segmentTimings.map(segment => {
        const speakerName = getCastMemberName(segment.speaker)
        return `${speakerName}: ${segment.text}`
      }).join('\n\n')
    }
    
    // Fallback to raw transcript
    return briefing?.transcript || ''
  }
  
  // Handle copying transcript to clipboard
  const handleCopyTranscript = async () => {
    const transcriptText = getTranscriptText()
    if (!transcriptText) return
    
    try {
      await navigator.clipboard.writeText(transcriptText)
    } catch (err) {
      console.error('Failed to copy transcript:', err)
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = transcriptText
      textArea.style.position = 'fixed'
      textArea.style.opacity = '0'
      document.body.appendChild(textArea)
      textArea.select()
      try {
        document.execCommand('copy')
      } catch (fallbackErr) {
        console.error('Fallback copy failed:', fallbackErr)
      }
      document.body.removeChild(textArea)
    }
  }
  
  // Handle downloading the audio file
  const handleDownload = async () => {
    if (!briefing?.audio_url) return
    
    try {
      // Fetch the audio file
      const response = await fetch(briefing.audio_url)
      if (!response.ok) {
        throw new Error('Failed to fetch audio file')
      }
      
      const blob = await response.blob()
      
      // Format date as YYYY-MM-DD
      const date = new Date(briefing.created_at)
      const dateStr = date.toISOString().split('T')[0]
      
      // Create a filename-safe version of the title
      const titleSlug = briefing.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .substring(0, 50) // Limit length
      
      // Construct filename: date-title-augustus.mp3
      const filename = `${dateStr}-${titleSlug}-augustus.mp3`
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download audio:', error)
      alert('Failed to download audio file. Please try again.')
    }
  }
  
  // Format timestamp as MM:SS
  const formatTimestamp = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }
  
  // Find the active chapter based on current time
  const findActiveChapter = useCallback((time: number): number | null => {
    for (let i = 0; i < chapters.length; i++) {
      const chapter = chapters[i]
      if (time >= chapter.start_time && (chapter.end_time === undefined || time < chapter.end_time)) {
        return i
      }
    }
    // If past all chapters, return last one
    if (chapters.length > 0 && time >= chapters[chapters.length - 1].start_time) {
      return chapters.length - 1
    }
    return null
  }, [chapters])
  
  // Track active chapter for highlighting
  const [activeChapterIndex, setActiveChapterIndex] = useState<number | null>(null)
  
  // Update active chapter based on audio playback using audioManager
  useEffect(() => {
    if (!isThisBriefingLoaded || currentAudio?.id !== id) {
      setActiveChapterIndex(null)
      return
    }
    
    const handleTimeUpdate = (time: number) => {
      const newActiveIndex = findActiveChapter(time)
      setActiveChapterIndex(newActiveIndex)
    }
    
    // Initial check
    const initialTime = audioManager.currentTime
    handleTimeUpdate(initialTime)
    
    // Subscribe to time updates from audioManager
    const unsubscribe = audioManager.onTimeUpdate(handleTimeUpdate)
    
    return () => {
      unsubscribe()
    }
  }, [isThisBriefingLoaded, currentAudio?.id, id, findActiveChapter])
  
  // Format transcript with proper styling for HOST1/HOST2
  // Uses segment timings if available for clickable timestamps
  // Integrates chapters as breaks within the transcript
  const formatTranscript = () => {
    // If we have segment timings, use them for clickable transcript
    if (segmentTimings.length > 0) {
      const elements: JSX.Element[] = []
      
      segmentTimings.forEach((segment, index) => {
        const isHost1 = segment.speaker.toUpperCase() === 'HOST1'
        const isActive = activeSegmentIndex === index
        
        // Check if a chapter starts at this segment's start time
        const chapterForSegment = chapters.find(
          ch => Math.abs(ch.start_time - segment.start_seconds) < 1.0 // Within 1 second
        )
        const chapterIndex = chapterForSegment ? chapters.indexOf(chapterForSegment) : null
        const isChapterActive = chapterIndex !== null && activeChapterIndex === chapterIndex
        
        // Insert chapter header before this segment if it matches
        if (chapterForSegment) {
          elements.push(
            <div
              key={`chapter-${chapterIndex}`}
              onClick={() => handleSeekToSegment(chapterForSegment.start_time)}
              className={clsx(
                'sticky top-0 z-10 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 sm:py-4 mb-4 sm:mb-6 mt-6 sm:mt-8 border-t border-b cursor-pointer transition-all duration-300 active:scale-[0.99]',
                'bg-augustus-900/95 backdrop-blur-sm',
                isChapterActive && isThisBriefingLoaded
                  ? 'border-accent/50'
                  : 'border-augustus-700 hover:border-augustus-600'
              )}
            >
              <div className="flex items-center justify-between">
                <h3 className={clsx(
                  'text-base sm:text-lg font-semibold',
                  isChapterActive && isThisBriefingLoaded ? 'text-accent' : 'text-augustus-300'
                )}>
                  {chapterForSegment.title}
                </h3>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleSeekToSegment(chapterForSegment.start_time)
                  }}
                  className={clsx(
                    'flex items-center gap-1 px-2 py-1 rounded text-xs font-mono transition-colors',
                    isChapterActive && isThisBriefingLoaded
                      ? 'bg-accent/40 text-white'
                      : 'bg-augustus-800/50 text-augustus-400 hover:bg-augustus-700/50'
                  )}
                >
                  <Play className="w-3 h-3" />
                  {formatTimestamp(chapterForSegment.start_time)}
                </button>
              </div>
            </div>
          )
        }
        
        // Add the segment
        elements.push(
          <div 
            key={index}
            ref={(el) => {
              if (el) segmentRefs.current.set(index, el)
            }}
            className={clsx(
              'mb-3 sm:mb-4 p-3 sm:p-4 rounded-lg cursor-pointer transition-all duration-300 active:scale-[0.99]',
              // Base styles
              isHost1 
                ? 'border-l-4 border-accent' 
                : 'border-l-4 border-purple-500',
              // Active state - highlighted with glow effect
              isActive && isThisBriefingLoaded
                ? isHost1
                  ? 'bg-accent/25 ring-2 ring-accent shadow-lg shadow-accent/20 scale-[1.01]'
                  : 'bg-purple-500/25 ring-2 ring-purple-500 shadow-lg shadow-purple-500/20 scale-[1.01]'
                : isHost1
                  ? 'bg-accent/10 hover:ring-2 hover:ring-accent/50 active:bg-accent/20'
                  : 'bg-purple-500/10 hover:ring-2 hover:ring-purple-500/50 active:bg-purple-500/20'
            )}
            onClick={() => handleSeekToSegment(segment.start_seconds)}
            title={`Tap to jump to ${formatTimestamp(segment.start_seconds)}`}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                {isActive && isCurrentlyPlaying && (
                  <Volume2 className={clsx(
                    'w-3.5 h-3.5 sm:w-4 sm:h-4 animate-pulse',
                    isHost1 ? 'text-accent' : 'text-purple-400'
                  )} />
                )}
                <span className={clsx(
                  'font-semibold text-xs sm:text-sm uppercase tracking-wide',
                  isHost1 ? 'text-accent' : 'text-purple-400'
                )}>
                  {getCastMemberName(segment.speaker)}
                </span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleSeekToSegment(segment.start_seconds)
                }}
                className={clsx(
                  'flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono transition-colors min-h-[28px]',
                  isActive && isThisBriefingLoaded
                    ? isHost1
                      ? 'bg-accent/40 text-white'
                      : 'bg-purple-500/40 text-white'
                    : isHost1 
                      ? 'bg-accent/20 text-accent hover:bg-accent/30 active:bg-accent/40' 
                      : 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 active:bg-purple-500/40'
                )}
              >
                <Play className="w-3 h-3" />
                {formatTimestamp(segment.start_seconds)}
              </button>
            </div>
            <p className={clsx(
              'transition-colors duration-300 text-sm sm:text-base',
              isActive && isThisBriefingLoaded ? 'text-white' : 'text-augustus-200'
            )}>{segment.text}</p>
          </div>
        )
      })
      
      return elements
    }
    
    // Fallback: parse transcript text if no segment timings
    const transcript = briefing?.transcript
    if (!transcript) return null
    
    const lines = transcript.split(/\n/)
    const formatted: JSX.Element[] = []
    
    lines.forEach((line, index) => {
      const trimmed = line.trim()
      if (!trimmed) {
        formatted.push(<br key={index} />)
        return
      }
      
      // Check for HOST1:, HOST2:, HOST3:, etc. prefix
      const hostMatch = trimmed.match(/^(HOST\d+):\s*(.*)$/i)
      if (hostMatch) {
        const [, host, content] = hostMatch
        const isHost1 = host.toUpperCase() === 'HOST1'
        formatted.push(
          <div key={index} className={clsx(
            'mb-3 sm:mb-4 p-3 sm:p-4 rounded-lg',
            isHost1 ? 'bg-accent/10 border-l-4 border-accent' : 'bg-purple-500/10 border-l-4 border-purple-500'
          )}>
            <span className={clsx(
              'font-semibold text-xs sm:text-sm uppercase tracking-wide',
              isHost1 ? 'text-accent' : 'text-purple-400'
            )}>
              {getCastMemberName(host)}
            </span>
            <p className="text-augustus-200 mt-1 text-sm sm:text-base">{content}</p>
          </div>
        )
      } else {
        formatted.push(
          <p key={index} className="text-augustus-300 mb-2 text-sm sm:text-base">{trimmed}</p>
        )
      }
    })
    
    return formatted
  }
  
  if (isLoading) {
    return (
      <div className="page-container flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  if (error || !briefing) {
    return (
      <div className="page-container">
        <button
          onClick={() => navigate('/dashboard')}
          className="btn btn-ghost mb-4 sm:mb-6 flex items-center gap-2"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>
        
        <div className="card text-center py-10 sm:py-12">
          <AlertCircle className="w-10 sm:w-12 h-10 sm:h-12 text-red-500 mx-auto mb-3 sm:mb-4" />
          <p className="text-sm sm:text-base text-augustus-400">Failed to load briefing</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="page-container max-w-4xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => navigate('/dashboard')}
        className="btn btn-ghost mb-4 sm:mb-6 flex items-center gap-2 text-augustus-400 hover:text-white -ml-2"
      >
        <ArrowLeft className="w-5 h-5" />
        <span className="sm:inline">Back</span>
      </button>
      
      {/* Header */}
      <div className="card mb-4 sm:mb-6">
        <div className="flex flex-col sm:flex-row items-start gap-4 sm:gap-6">
          {/* Play button */}
          <button
            onClick={handlePlayPause}
            disabled={briefing.status !== 'completed'}
            className={clsx(
              'w-16 h-16 sm:w-20 sm:h-20 rounded-full flex items-center justify-center flex-shrink-0 transition-all self-center sm:self-start',
              briefing.status === 'completed'
                ? 'bg-accent hover:bg-accent-600 text-white glow active:scale-95'
                : 'bg-augustus-800 text-augustus-500'
            )}
          >
            {briefing.status === 'generating' || briefing.status === 'pending' ? (
              <Loader2 className="w-7 h-7 sm:w-8 sm:h-8 animate-spin" />
            ) : briefing.status === 'failed' ? (
              <AlertCircle className="w-7 h-7 sm:w-8 sm:h-8 text-red-500" />
            ) : isCurrentlyPlaying ? (
              <Pause className="w-7 h-7 sm:w-8 sm:h-8" />
            ) : (
              <Play className="w-7 h-7 sm:w-8 sm:h-8 ml-1" />
            )}
          </button>
          
          {/* Info */}
          <div className="flex-1 text-center sm:text-left">
            {/* Topics */}
            {(() => {
              const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
              const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
              
              if (briefingTopics.length === 0) return null
              
              return (
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-1.5 sm:gap-2 mb-3">
                  {briefingTopics.map((topic) => (
                    <span
                      key={topic.id}
                        className="px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full text-xs font-medium flex items-center gap-1.5"
                        style={{ backgroundColor: `${topic.color || '#3B82F6'}20`, color: topic.color || '#3B82F6' }}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                          style={{ backgroundColor: topic.color || '#3B82F6' }}
                        />
                        {topic.name}
                      </span>
                    ))}
                  </div>
                )
              })()}
            
            <h1 className="text-xl sm:text-2xl font-display font-semibold text-white mb-2">
              {briefing.title}
            </h1>
            
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 sm:gap-4 text-xs sm:text-sm text-augustus-400">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                {formatDuration(briefing.duration_seconds)}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                {formatDate(briefing.created_at)}
              </span>
              <span className={clsx(
                'px-2 py-0.5 rounded-full text-xs font-medium',
                briefing.status === 'completed' && 'bg-green-500/20 text-green-400',
                briefing.status === 'generating' && 'bg-yellow-500/20 text-yellow-400',
                briefing.status === 'pending' && 'bg-augustus-700 text-augustus-400',
                briefing.status === 'failed' && 'bg-red-500/20 text-red-400',
              )}>
                {briefing.status}
              </span>
              {/* Listened indicator */}
              {briefing.status === 'completed' && (
                <span className={clsx(
                  'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
                  briefing.listened 
                    ? 'bg-accent/20 text-accent' 
                    : 'bg-augustus-700 text-augustus-400'
                )}>
                  {briefing.listened ? (
                    <>
                      <CheckCircle className="w-3 h-3" />
                      <span className="hidden sm:inline">Listened</span>
                    </>
                  ) : (
                    <>
                      <Circle className="w-3 h-3" />
                      <span className="hidden sm:inline">Not Listened</span>
                    </>
                  )}
                </span>
              )}
            </div>
            
            {/* Summary */}
            {briefing.status === 'completed' && briefing.extra_data?.story_analysis_raw && (
              <p className="text-sm sm:text-base text-augustus-300 leading-relaxed mt-3 sm:mt-4">
                {briefing.extra_data.story_analysis_raw as string}
              </p>
            )}
            
            {briefing.error_message && (
              <p className="text-sm text-red-400 mt-2">{briefing.error_message}</p>
            )}
          </div>
          
        </div>
      </div>
      
      {/* Action Bar */}
      {briefing.status === 'completed' && (briefing.transcript || segmentTimings.length > 0 || briefing.audio_url) && (
        <div className="card mb-4 sm:mb-6">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <button
              onClick={() => favoriteMutation.mutate({ favorite: !briefing.favorite })}
              disabled={favoriteMutation.isPending}
              className={clsx(
                'btn btn-ghost flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed',
                briefing.favorite && 'text-red-500 hover:text-red-400'
              )}
              title={briefing.favorite ? 'Remove from favorites' : 'Add to favorites'}
            >
              {favoriteMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Heart className={clsx('w-4 h-4', briefing.favorite && 'fill-current')} />
              )}
              <span className="hidden sm:inline">Favorite</span>
            </button>
            
            <button
              onClick={handleCopyTranscript}
              disabled={!briefing.transcript && segmentTimings.length === 0}
              className="btn btn-ghost flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              title="Copy transcript"
            >
              <Copy className="w-4 h-4" />
              <span className="hidden sm:inline">Copy</span>
            </button>
            
            <button
              onClick={handleDownload}
              disabled={!briefing.audio_url}
              className="btn btn-ghost flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              title="Download audio file"
            >
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">Download</span>
            </button>
            
            <button
              onClick={() => listenedMutation.mutate({ listened: !briefing.listened })}
              disabled={listenedMutation.isPending}
              className="btn btn-ghost flex items-center gap-2 text-sm"
              title={briefing.listened ? 'Mark as Not Listened' : 'Mark as Listened'}
            >
              {listenedMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : briefing.listened ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <Circle className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">
                {briefing.listened ? 'Not Listened' : 'Listened'}
              </span>
            </button>
            
            <button
              onClick={() => setShowCreateScheduleModal(true)}
              className="btn btn-ghost flex items-center gap-2 text-sm"
              title="Create Schedule"
            >
              <CalendarClock className="w-4 h-4" />
              <span className="hidden sm:inline">Schedule</span>
            </button>
            
            <button
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="btn btn-ghost flex items-center gap-2 text-sm text-red-400 hover:text-red-300"
              title="Delete briefing"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">Delete</span>
            </button>
          </div>
        </div>
      )}
      
      {/* Transcript */}
      {(briefing.transcript || segmentTimings.length > 0) && (
        <div className="card" ref={transcriptContainerRef}>
          <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-accent" />
            Transcript
            {segmentTimings.length > 0 && (
              <span className="text-xs font-normal text-augustus-400 ml-1 sm:ml-2">
                (tap to jump)
              </span>
            )}
          </h2>
          
          <div className="prose prose-invert max-w-none">
            {formatTranscript()}
          </div>
        </div>
      )}

      {/* Scroll to Transcript Pill - positioned above audio player */}
      {showScrollToTranscript && isCurrentlyPlaying && (
        <button
          onClick={handleScrollToTranscript}
          className="fixed left-1/2 transform -translate-x-1/2 z-50 
                     bg-accent hover:bg-accent-600 text-white 
                     px-4 py-2 rounded-full shadow-lg 
                     flex items-center gap-2 
                     transition-all duration-300 
                     hover:scale-105 active:scale-95
                     bottom-44 md:bottom-36"
          style={{
            // Add safe area inset for devices with home indicator
            marginBottom: 'env(safe-area-inset-bottom, 0px)'
          }}
        >
          <Navigation2 className="w-4 h-4" />
          <span className="text-sm font-medium">Follow Transcript</span>
        </button>
      )}
      
      {/* Sources */}
      {((briefing.sources && briefing.sources.length > 0) || 
        (briefing.extra_data?.story_analysis_raw || briefing.extra_data?.facts_analysis_raw) ||
        (briefing.status === 'completed')) && (
        <div className="card mt-4 sm:mt-6">
          {briefing.sources && briefing.sources.length > 0 && (
            <>
              <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">
                Sources ({briefing.sources.length})
              </h2>
              
              <div className="space-y-2 sm:space-y-3">
                {briefing.sources.map((source, index) => (
                  <a
                    key={index}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-3 rounded-lg bg-augustus-900/50 hover:bg-augustus-800/50 active:bg-augustus-700/50 transition-colors"
                  >
                    <div className="flex items-start gap-2">
                      <ExternalLink className="w-4 h-4 text-augustus-500 flex-shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <h3 className="text-white font-medium text-sm">
                          {source.title}
                        </h3>
                        {source.summary && (
                          <p className="text-augustus-400 text-xs mt-1 line-clamp-2">
                            {source.summary}
                          </p>
                        )}
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            </>
          )}
          
          {/* Briefing Notes Accordion */}
          {(briefing.extra_data?.story_analysis_raw || briefing.extra_data?.facts_analysis_raw) && (
            <div className="mt-4 sm:mt-6 pt-4 sm:pt-6 border-t border-augustus-700">
              <button
                onClick={() => setNotesExpanded(!notesExpanded)}
                className="w-full flex items-center justify-between gap-2 text-left"
              >
                <h3 className="text-sm sm:text-base font-semibold text-white flex items-center gap-2">
                  <BookOpen className="w-4 h-4 sm:w-5 sm:h-5 text-accent" />
                  Briefing Notes
                </h3>
                <ChevronDown 
                  className={clsx(
                    'w-4 h-4 sm:w-5 sm:h-5 text-augustus-400 transition-transform duration-200',
                    notesExpanded && 'rotate-180'
                  )}
                />
              </button>
              
              {notesExpanded && (
                <div className="mt-3 sm:mt-4 space-y-4">
                  {briefing.extra_data?.story_analysis_raw && (
                    <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                      <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-2">Story Analysis</h4>
                      <pre className="text-xs sm:text-sm text-augustus-300 whitespace-pre-wrap leading-relaxed font-mono overflow-x-auto">
                        {briefing.extra_data.story_analysis_raw}
                      </pre>
                    </div>
                  )}
                  {briefing.extra_data?.facts_analysis_raw && (
                    <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                      <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-2">Facts Analysis</h4>
                      <pre className="text-xs sm:text-sm text-augustus-300 whitespace-pre-wrap leading-relaxed font-mono overflow-x-auto">
                        {briefing.extra_data.facts_analysis_raw}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          
          {/* Nerd Stats Accordion */}
          {briefing.status === 'completed' && (
            <div className="mt-4 sm:mt-6 pt-4 sm:pt-6 border-t border-augustus-700">
              <button
                onClick={() => setNerdStatsExpanded(!nerdStatsExpanded)}
                className="w-full flex items-center justify-between gap-2 text-left"
              >
                <h3 className="text-sm sm:text-base font-semibold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 sm:w-5 sm:h-5 text-accent" />
                  Nerd Stats
                </h3>
                <ChevronDown 
                  className={clsx(
                    'w-4 h-4 sm:w-5 sm:h-5 text-augustus-400 transition-transform duration-200',
                    nerdStatsExpanded && 'rotate-180'
                  )}
                />
              </button>
              
              {nerdStatsExpanded && (
                <div className="mt-3 sm:mt-4 space-y-4">
                  {/* Time to Generation */}
                  {briefing.created_at && briefing.generated_at && (
                    <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                      <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-3 flex items-center gap-2">
                        <Zap className="w-4 h-4 text-accent" />
                        Time to Generation
                      </h4>
                      <div className="space-y-2 text-xs sm:text-sm">
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Total Time:</span>
                          <span className="text-white font-mono">
                            {(() => {
                              const created = new Date(briefing.created_at)
                              const generated = new Date(briefing.generated_at)
                              const diffMs = generated.getTime() - created.getTime()
                              const diffSec = Math.floor(diffMs / 1000)
                              const minutes = Math.floor(diffSec / 60)
                              const seconds = diffSec % 60
                              return minutes > 0 
                                ? `${minutes}m ${seconds}s`
                                : `${seconds}s`
                            })()}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Created:</span>
                          <span className="text-augustus-300 font-mono text-xs">
                            {new Date(briefing.created_at).toLocaleString()}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Generated:</span>
                          <span className="text-augustus-300 font-mono text-xs">
                            {new Date(briefing.generated_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* Audio File Details */}
                  {briefing.audio_filename && (
                    <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                      <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-3 flex items-center gap-2">
                        <FileAudio className="w-4 h-4 text-accent" />
                        Audio File Details
                      </h4>
                      <div className="space-y-2 text-xs sm:text-sm">
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Filename:</span>
                          <span className="text-white font-mono text-xs break-all text-right ml-2">
                            {briefing.audio_filename}
                          </span>
                        </div>
                        {briefing.duration_seconds && (
                          <div className="flex justify-between">
                            <span className="text-augustus-400">Duration:</span>
                            <span className="text-white font-mono">
                              {formatDuration(briefing.duration_seconds)}
                            </span>
                          </div>
                        )}
                        {audioFileSize !== null && (
                          <div className="flex justify-between">
                            <span className="text-augustus-400">File Size:</span>
                            <span className="text-white font-mono">
                              {formatFileSize(audioFileSize)}
                            </span>
                          </div>
                        )}
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Format:</span>
                          <span className="text-white font-mono">MP3</span>
                        </div>
                        {briefing.extra_data?.segment_timings && (
                          <div className="flex justify-between">
                            <span className="text-augustus-400">Segments:</span>
                            <span className="text-white font-mono">
                              {Array.isArray(briefing.extra_data.segment_timings) 
                                ? briefing.extra_data.segment_timings.length 
                                : 0}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Generation Details */}
                  <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                    <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-3 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-accent" />
                      Generation Details
                    </h4>
                    <div className="space-y-2 text-xs sm:text-sm">
                      {briefing.extra_data?.stories_analyzed !== undefined && (
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Stories Analyzed:</span>
                          <span className="text-white font-mono">
                            {briefing.extra_data.stories_analyzed}
                          </span>
                        </div>
                      )}
                      {briefing.extra_data?.stories_selected !== undefined && (
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Stories Selected:</span>
                          <span className="text-white font-mono">
                            {briefing.extra_data.stories_selected}
                          </span>
                        </div>
                      )}
                      {briefing.chapters && briefing.chapters.length > 0 && (
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Chapters:</span>
                          <span className="text-white font-mono">
                            {briefing.chapters.length}
                          </span>
                        </div>
                      )}
                      {briefing.sources && (
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Sources:</span>
                          <span className="text-white font-mono">
                            {briefing.sources.length}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* LLM Details */}
                  {briefing.extra_data?.model && (
                    <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                      <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-3 flex items-center gap-2">
                        <Cpu className="w-4 h-4 text-accent" />
                        LLM Details
                      </h4>
                      <div className="space-y-2 text-xs sm:text-sm">
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Model:</span>
                          <span className="text-white font-mono text-xs break-all text-right ml-2">
                            {String(briefing.extra_data.model)}
                          </span>
                        </div>
                        {briefing.extra_data?.usage && typeof briefing.extra_data.usage === 'object' && (
                          <>
                            {briefing.extra_data.usage.prompt_tokens !== undefined && (
                              <div className="flex justify-between">
                                <span className="text-augustus-400">Prompt Tokens:</span>
                                <span className="text-white font-mono">
                                  {briefing.extra_data.usage.prompt_tokens.toLocaleString()}
                                </span>
                              </div>
                            )}
                            {briefing.extra_data.usage.completion_tokens !== undefined && (
                              <div className="flex justify-between">
                                <span className="text-augustus-400">Completion Tokens:</span>
                                <span className="text-white font-mono">
                                  {briefing.extra_data.usage.completion_tokens.toLocaleString()}
                                </span>
                              </div>
                            )}
                            {briefing.extra_data.usage.total_tokens !== undefined && (
                              <div className="flex justify-between">
                                <span className="text-augustus-400">Total Tokens:</span>
                                <span className="text-white font-mono">
                                  {briefing.extra_data.usage.total_tokens.toLocaleString()}
                                </span>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* TTS Details */}
                  {settings && (
                    <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                      <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-3 flex items-center gap-2">
                        <Volume2 className="w-4 h-4 text-accent" />
                        TTS Details
                      </h4>
                      <div className="space-y-2 text-xs sm:text-sm">
                        <div className="flex justify-between">
                          <span className="text-augustus-400">Provider:</span>
                          <span className="text-white font-mono capitalize">
                            {settings.tts_provider || 'Unknown'}
                          </span>
                        </div>
                        {briefing.extra_data?.tts_voice && (
                          <div className="flex justify-between">
                            <span className="text-augustus-400">Voice:</span>
                            <span className="text-white font-mono text-xs break-all text-right ml-2">
                              {String(briefing.extra_data.tts_voice)}
                            </span>
                          </div>
                        )}
                        {settings.tts_provider === 'piper' && settings.piper_model && (
                          <div className="flex justify-between">
                            <span className="text-augustus-400">Piper Model:</span>
                            <span className="text-white font-mono text-xs break-all text-right ml-2">
                              {settings.piper_model}
                            </span>
                          </div>
                        )}
                        {settings.tts_provider === 'elevenlabs' && settings.elevenlabs_model && (
                          <div className="flex justify-between">
                            <span className="text-augustus-400">ElevenLabs Model:</span>
                            <span className="text-white font-mono text-xs break-all text-right ml-2">
                              {settings.elevenlabs_model}
                            </span>
                          </div>
                        )}
                        {settings.tts_provider === 'gemini' && settings.gemini_model && (
                          <div className="flex justify-between">
                            <span className="text-augustus-400">Gemini Model:</span>
                            <span className="text-white font-mono text-xs break-all text-right ml-2">
                              {settings.gemini_model}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Costs Breakdown */}
                  {briefing.extra_data?.costs && (
                    <div className="p-3 sm:p-4 rounded-lg bg-augustus-900/50">
                      <h4 className="text-xs sm:text-sm font-semibold text-augustus-200 mb-3 flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-accent" />
                        Costs
                      </h4>
                      <div className="space-y-3 text-xs sm:text-sm">
                        {briefing.extra_data.costs.story_analysis && (
                          <div className="space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="text-augustus-400">Story Analysis:</span>
                              <span className="text-white font-mono">
                                ${(briefing.extra_data.costs.story_analysis.cost || 0).toFixed(6)}
                              </span>
                            </div>
                            {briefing.extra_data.costs.story_analysis.total_tokens && (
                              <div className="flex justify-between text-augustus-500 text-xs ml-4">
                                <span>{briefing.extra_data.costs.story_analysis.total_tokens.toLocaleString()} tokens</span>
                              </div>
                            )}
                          </div>
                        )}
                        {briefing.extra_data.costs.facts_gathering && (
                          <div className="space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="text-augustus-400">Facts Gathering:</span>
                              <span className="text-white font-mono">
                                ${(briefing.extra_data.costs.facts_gathering.cost || 0).toFixed(6)}
                              </span>
                            </div>
                            {briefing.extra_data.costs.facts_gathering.total_tokens && (
                              <div className="flex justify-between text-augustus-500 text-xs ml-4">
                                <span>{briefing.extra_data.costs.facts_gathering.total_tokens.toLocaleString()} tokens</span>
                              </div>
                            )}
                          </div>
                        )}
                        {briefing.extra_data.costs.script_writing && (
                          <div className="space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="text-augustus-400">Script Writing:</span>
                              <span className="text-white font-mono">
                                ${(briefing.extra_data.costs.script_writing.cost || 0).toFixed(6)}
                              </span>
                            </div>
                            {briefing.extra_data.costs.script_writing.total_tokens && (
                              <div className="flex justify-between text-augustus-500 text-xs ml-4">
                                <span>{briefing.extra_data.costs.script_writing.total_tokens.toLocaleString()} tokens</span>
                              </div>
                            )}
                          </div>
                        )}
                        {briefing.extra_data.costs.tts_generation && (
                          <div className="space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="text-augustus-400">TTS Generation:</span>
                              <span className="text-white font-mono">
                                ${(briefing.extra_data.costs.tts_generation.cost || 0).toFixed(6)}
                              </span>
                            </div>
                            {briefing.extra_data.costs.tts_generation.characters && (
                              <div className="flex justify-between text-augustus-500 text-xs ml-4">
                                <span>{briefing.extra_data.costs.tts_generation.characters.toLocaleString()} chars</span>
                                {briefing.extra_data.costs.tts_generation.duration_seconds && (
                                  <span>{Math.round(briefing.extra_data.costs.tts_generation.duration_seconds)}s</span>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                        {briefing.extra_data.costs.total !== undefined && (
                          <div className="pt-2 mt-2 border-t border-augustus-700">
                            <div className="flex justify-between items-center">
                              <span className="text-augustus-200 font-semibold">Total:</span>
                              <span className="text-white font-mono font-semibold">
                                ${(briefing.extra_data.costs.total || 0).toFixed(6)}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Create Schedule Modal */}
      {showCreateScheduleModal && (
        <CreateScheduleModal
          isOpen={showCreateScheduleModal}
          onClose={() => setShowCreateScheduleModal(false)}
          onConfirm={(scheduleTime, scheduleDays) => {
            createScheduleMutation.mutate({
              schedule_time: scheduleTime,
              schedule_days: scheduleDays,
            })
          }}
          isLoading={createScheduleMutation.isPending}
          timezone={timezone}
        />
      )}
    </div>
  )
}

// Create Schedule Modal Component
interface CreateScheduleModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (scheduleTime: string, scheduleDays: number[]) => void
  isLoading: boolean
  timezone: string
}

function CreateScheduleModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
  timezone,
}: CreateScheduleModalProps) {
  const [hours, setHours] = useState(8)
  const [minutes, setMinutes] = useState(0)
  const [selectedDays, setSelectedDays] = useState<number[]>([0, 1, 2, 3, 4]) // Mon-Fri by default
  
  const DAYS_OF_WEEK = [
    { value: 0, label: 'Mon', fullLabel: 'Monday' },
    { value: 1, label: 'Tue', fullLabel: 'Tuesday' },
    { value: 2, label: 'Wed', fullLabel: 'Wednesday' },
    { value: 3, label: 'Thu', fullLabel: 'Thursday' },
    { value: 4, label: 'Fri', fullLabel: 'Friday' },
    { value: 5, label: 'Sat', fullLabel: 'Saturday' },
    { value: 6, label: 'Sun', fullLabel: 'Sunday' },
  ]
  
  const handleDayToggle = (day: number) => {
    setSelectedDays(prev => 
      prev.includes(day) 
        ? prev.filter(d => d !== day)
        : [...prev, day]
    )
  }
  
  const handleConfirm = () => {
    const scheduleTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`
    onConfirm(scheduleTime, selectedDays)
  }
  
  if (!isOpen) return null
  
  return (
    <>
      <div 
        className="fixed inset-0 bg-black/50 z-[200]" 
        onClick={onClose}
      />
      <div className="fixed inset-0 z-[201] flex items-center justify-center p-4">
        <div 
          className="bg-augustus-900 border border-augustus-700 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6 sm:p-8">
            <h2 className="text-xl sm:text-2xl font-semibold text-white mb-6">
              Create Schedule
            </h2>
            
            {/* Time Selection with Big Numbers */}
            <div className="mb-8">
              <label className="block text-sm font-medium text-augustus-300 mb-4">
                Schedule Time ({timezone})
              </label>
              <div className="flex items-center justify-center gap-4 sm:gap-8">
                {/* Hours */}
                <div className="flex flex-col items-center">
                  <label className="text-xs text-augustus-400 mb-2 uppercase tracking-wide">Hours</label>
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => setHours(prev => Math.min(23, prev + 1))}
                      className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
                      disabled={isLoading}
                    >
                      <ChevronUp className="w-4 h-4" />
                    </button>
                    <div className="text-6xl sm:text-8xl font-bold text-white tabular-nums min-w-[80px] sm:min-w-[120px] text-center">
                      {hours.toString().padStart(2, '0')}
                    </div>
                    <button
                      onClick={() => setHours(prev => Math.max(0, prev - 1))}
                      className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
                      disabled={isLoading}
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                
                {/* Separator */}
                <div className="text-6xl sm:text-8xl font-bold text-augustus-600 pb-8">
                  :
                </div>
                
                {/* Minutes */}
                <div className="flex flex-col items-center">
                  <label className="text-xs text-augustus-400 mb-2 uppercase tracking-wide">Minutes</label>
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => setMinutes(prev => Math.min(59, prev + 1))}
                      className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
                      disabled={isLoading}
                    >
                      <ChevronUp className="w-4 h-4" />
                    </button>
                    <div className="text-6xl sm:text-8xl font-bold text-white tabular-nums min-w-[80px] sm:min-w-[120px] text-center">
                      {minutes.toString().padStart(2, '0')}
                    </div>
                    <button
                      onClick={() => setMinutes(prev => Math.max(0, prev - 1))}
                      className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
                      disabled={isLoading}
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Days Selection */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-augustus-300 mb-4">
                Days of Week
              </label>
              <div className="flex flex-wrap gap-2">
                {DAYS_OF_WEEK.map(day => (
                  <button
                    key={day.value}
                    onClick={() => handleDayToggle(day.value)}
                    disabled={isLoading}
                    className={clsx(
                      'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      selectedDays.includes(day.value)
                        ? 'bg-accent text-white'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                    )}
                  >
                    {day.label}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-augustus-700">
              <button
                onClick={onClose}
                disabled={isLoading}
                className="btn btn-ghost"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={isLoading || selectedDays.length === 0}
                className="btn btn-primary"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Creating...
                  </>
                ) : (
                  'Create Schedule'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
