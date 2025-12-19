import { useParams, useNavigate } from 'react-router-dom'
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
  MoreVertical,
  CheckCircle,
  Circle,
  Check
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, settingsApi, castsApi, SegmentTiming } from '../api/client'
import { useStore } from '../store/useStore'
import { formatFullDate } from '../utils/timezone'

export default function BriefingDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const segmentRefs = useRef<Map<number, HTMLDivElement>>(new Map())
  
  const currentAudio = useStore((s) => s.currentAudio)
  const isPlaying = useStore((s) => s.isPlaying)
  const setCurrentAudio = useStore((s) => s.setCurrentAudio)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  
  // Track active segment for highlighting
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null)
  const [showMenu, setShowMenu] = useState(false)
  
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
      setShowMenu(false)
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
  
  // Set up audio time tracking
  useEffect(() => {
    if (!briefing?.audio_filename || !isThisBriefingLoaded) {
      setActiveSegmentIndex(null)
      return
    }
    
    // Find the audio element
    const findAudioElement = () => {
      const audioElements = document.querySelectorAll('audio')
      for (const el of audioElements) {
        if (el.src.includes(briefing.audio_filename || '')) {
          return el
        }
      }
      return null
    }
    
    const audio = findAudioElement()
    if (!audio) return
    
    audioRef.current = audio
    
    // Update time handler
    const handleTimeUpdate = () => {
      const time = audio.currentTime
      const newActiveIndex = findActiveSegment(time)
      setActiveSegmentIndex(newActiveIndex)
    }
    
    // Initial check
    handleTimeUpdate()
    
    // Listen for time updates
    audio.addEventListener('timeupdate', handleTimeUpdate)
    
    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate)
    }
  }, [briefing?.audio_filename, isThisBriefingLoaded, findActiveSegment])
  
  // Auto-scroll to active segment
  useEffect(() => {
    if (activeSegmentIndex !== null && isCurrentlyPlaying) {
      const segmentEl = segmentRefs.current.get(activeSegmentIndex)
      if (segmentEl) {
        segmentEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }, [activeSegmentIndex, isCurrentlyPlaying])
  
  const handlePlayPause = () => {
    if (!briefing?.audio_url) return
    
    if (currentAudio?.id === id) {
      // Toggle play/pause for current audio
      setIsPlaying(!isPlaying)
    } else {
      // Start playing this briefing, resuming from saved position if available
      setCurrentAudio({
        id: briefing.id,
        type: 'briefing',
        title: briefing.title,
        audioUrl: briefing.audio_url,
        transcript: briefing.transcript,
        chapters: briefing.chapters,
        initialPosition: briefing.playback_position || undefined,
      })
      setIsPlaying(true)
    }
  }
  
  const handleSeekToSegment = (startSeconds: number) => {
    // First, ensure the audio is loaded
    if (!briefing?.audio_url) return
    
    // If not currently playing this briefing, start it first
    if (currentAudio?.id !== id) {
      setCurrentAudio({
        id: briefing.id,
        type: 'briefing',
        title: briefing.title,
        audioUrl: briefing.audio_url,
        transcript: briefing.transcript,
        chapters: briefing.chapters,
        initialPosition: startSeconds,  // Use the segment start as initial position
      })
      setIsPlaying(true)
      
      // Wait a bit for the audio element to be created, then seek
      setTimeout(() => {
        const audioElements = document.querySelectorAll('audio')
        audioElements.forEach((el) => {
          if (el.src.includes(briefing.audio_filename || '')) {
            el.currentTime = startSeconds
          }
        })
      }, 100)
    } else {
      // Already playing this briefing, just seek
      const audioElements = document.querySelectorAll('audio')
      audioElements.forEach((el) => {
        if (el.src.includes(briefing.audio_filename || '')) {
          el.currentTime = startSeconds
          if (!isPlaying) {
            setIsPlaying(true)
          }
        }
      })
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
  
  // Update active chapter based on audio playback
  useEffect(() => {
    if (!briefing?.audio_filename || !isThisBriefingLoaded) {
      setActiveChapterIndex(null)
      return
    }
    
    const findAudioElement = () => {
      const audioElements = document.querySelectorAll('audio')
      for (const el of audioElements) {
        if (el.src.includes(briefing.audio_filename || '')) {
          return el
        }
      }
      return null
    }
    
    const audio = findAudioElement()
    if (!audio) return
    
    const handleTimeUpdate = () => {
      const time = audio.currentTime
      const newActiveIndex = findActiveChapter(time)
      setActiveChapterIndex(newActiveIndex)
    }
    
    handleTimeUpdate()
    audio.addEventListener('timeupdate', handleTimeUpdate)
    
    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate)
    }
  }, [briefing?.audio_filename, isThisBriefingLoaded, findActiveChapter])
  
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
                'mb-4 sm:mb-6 mt-6 sm:mt-8 pt-4 sm:pt-6 border-t border-augustus-700 cursor-pointer transition-all duration-300 active:scale-[0.99]',
                isChapterActive && isThisBriefingLoaded
                  ? 'border-accent/50'
                  : 'hover:border-augustus-600'
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
                      <span className="hidden sm:inline">Unlistened</span>
                    </>
                  )}
                </span>
              )}
            </div>
            
            {briefing.error_message && (
              <p className="text-sm text-red-400 mt-2">{briefing.error_message}</p>
            )}
          </div>
          
          {/* Menu button */}
          {briefing.status === 'completed' && (
            <div className="relative absolute top-4 right-4 sm:static">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
              >
                <MoreVertical className="w-5 h-5" />
              </button>
              
              {/* Dropdown menu */}
              {showMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-10" 
                    onClick={() => setShowMenu(false)}
                  />
                  <div className="absolute right-0 top-full mt-2 w-56 bg-augustus-900 border border-augustus-700 rounded-lg shadow-xl z-20 overflow-hidden">
                    <div className="py-1">
                      <button
                        onClick={() => listenedMutation.mutate({ listened: !briefing.listened })}
                        disabled={listenedMutation.isPending}
                        className="w-full px-4 py-3 text-left hover:bg-augustus-800 active:bg-augustus-700 transition-colors flex items-center gap-3"
                      >
                        {listenedMutation.isPending ? (
                          <Loader2 className="w-5 h-5 animate-spin text-augustus-400" />
                        ) : briefing.listened ? (
                          <Circle className="w-5 h-5 text-augustus-400" />
                        ) : (
                          <Check className="w-5 h-5 text-accent" />
                        )}
                        <div>
                          <span className="text-white font-medium block text-sm">
                            {briefing.listened ? 'Mark as unlistened' : 'Mark as listened'}
                          </span>
                        </div>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Transcript */}
      {(briefing.transcript || segmentTimings.length > 0) && (
        <div className="card">
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
      
      {/* Sources */}
      {briefing.sources && briefing.sources.length > 0 && (
        <div className="card mt-4 sm:mt-6">
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
        </div>
      )}
    </div>
  )
}
