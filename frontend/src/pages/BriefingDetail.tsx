import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useEffect, useState, useCallback } from 'react'
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
import { briefingsApi, settingsApi, SegmentTiming } from '../api/client'
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
      // Start playing this briefing
      setCurrentAudio({
        id: briefing.id,
        type: 'briefing',
        title: briefing.title,
        audioUrl: briefing.audio_url,
        transcript: briefing.transcript,
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
  
  // Format transcript with proper styling for HOST1/HOST2
  // Uses segment timings if available for clickable timestamps
  const formatTranscript = () => {
    // If we have segment timings, use them for clickable transcript
    if (segmentTimings.length > 0) {
      return segmentTimings.map((segment, index) => {
        const isHost1 = segment.speaker.toUpperCase() === 'HOST1'
        const isActive = activeSegmentIndex === index
        
        return (
          <div 
            key={index}
            ref={(el) => {
              if (el) segmentRefs.current.set(index, el)
            }}
            className={clsx(
              'mb-4 p-4 rounded-lg cursor-pointer transition-all duration-300',
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
                  ? 'bg-accent/10 hover:ring-2 hover:ring-accent/50'
                  : 'bg-purple-500/10 hover:ring-2 hover:ring-purple-500/50'
            )}
            onClick={() => handleSeekToSegment(segment.start_seconds)}
            title={`Click to jump to ${formatTimestamp(segment.start_seconds)}`}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                {isActive && isCurrentlyPlaying && (
                  <Volume2 className={clsx(
                    'w-4 h-4 animate-pulse',
                    isHost1 ? 'text-accent' : 'text-purple-400'
                  )} />
                )}
                <span className={clsx(
                  'font-semibold text-sm uppercase tracking-wide',
                  isHost1 ? 'text-accent' : 'text-purple-400'
                )}>
                  {isHost1 ? 'Alex (Host 1)' : 'Sam (Host 2)'}
                </span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleSeekToSegment(segment.start_seconds)
                }}
                className={clsx(
                  'flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono transition-colors',
                  isActive && isThisBriefingLoaded
                    ? isHost1
                      ? 'bg-accent/40 text-white'
                      : 'bg-purple-500/40 text-white'
                    : isHost1 
                      ? 'bg-accent/20 text-accent hover:bg-accent/30' 
                      : 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30'
                )}
              >
                <Play className="w-3 h-3" />
                {formatTimestamp(segment.start_seconds)}
              </button>
            </div>
            <p className={clsx(
              'transition-colors duration-300',
              isActive && isThisBriefingLoaded ? 'text-white' : 'text-augustus-200'
            )}>{segment.text}</p>
          </div>
        )
      })
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
      
      // Check for HOST1: or HOST2: prefix
      const hostMatch = trimmed.match(/^(HOST[12]):\s*(.*)$/i)
      if (hostMatch) {
        const [, host, content] = hostMatch
        const isHost1 = host.toUpperCase() === 'HOST1'
        formatted.push(
          <div key={index} className={clsx(
            'mb-4 p-4 rounded-lg',
            isHost1 ? 'bg-accent/10 border-l-4 border-accent' : 'bg-purple-500/10 border-l-4 border-purple-500'
          )}>
            <span className={clsx(
              'font-semibold text-sm uppercase tracking-wide',
              isHost1 ? 'text-accent' : 'text-purple-400'
            )}>
              {isHost1 ? 'Alex (Host 1)' : 'Sam (Host 2)'}
            </span>
            <p className="text-augustus-200 mt-1">{content}</p>
          </div>
        )
      } else {
        formatted.push(
          <p key={index} className="text-augustus-300 mb-2">{trimmed}</p>
        )
      }
    })
    
    return formatted
  }
  
  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  if (error || !briefing) {
    return (
      <div className="p-8">
        <button
          onClick={() => navigate('/dashboard')}
          className="btn btn-ghost mb-6 flex items-center gap-2"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Dashboard
        </button>
        
        <div className="card text-center py-12">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-augustus-400">Failed to load briefing</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => navigate('/dashboard')}
        className="btn btn-ghost mb-6 flex items-center gap-2 text-augustus-400 hover:text-white"
      >
        <ArrowLeft className="w-5 h-5" />
        Back to Dashboard
      </button>
      
      {/* Header */}
      <div className="card mb-6">
        <div className="flex items-start gap-6">
          {/* Play button */}
          <button
            onClick={handlePlayPause}
            disabled={briefing.status !== 'completed'}
            className={clsx(
              'w-20 h-20 rounded-full flex items-center justify-center flex-shrink-0 transition-all',
              briefing.status === 'completed'
                ? 'bg-accent hover:bg-accent-600 text-white glow'
                : 'bg-augustus-800 text-augustus-500'
            )}
          >
            {briefing.status === 'generating' || briefing.status === 'pending' ? (
              <Loader2 className="w-8 h-8 animate-spin" />
            ) : briefing.status === 'failed' ? (
              <AlertCircle className="w-8 h-8 text-red-500" />
            ) : isCurrentlyPlaying ? (
              <Pause className="w-8 h-8" />
            ) : (
              <Play className="w-8 h-8 ml-1" />
            )}
          </button>
          
          {/* Info */}
          <div className="flex-1">
            <h1 className="text-2xl font-display font-semibold text-white mb-2">
              {briefing.title}
            </h1>
            
            <div className="flex flex-wrap items-center gap-4 text-sm text-augustus-400">
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {formatDuration(briefing.duration_seconds)}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
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
                      Listened
                    </>
                  ) : (
                    <>
                      <Circle className="w-3 h-3" />
                      Unlistened
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
            <div className="relative">
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
                        className="w-full px-4 py-3 text-left hover:bg-augustus-800 transition-colors flex items-center gap-3"
                      >
                        {listenedMutation.isPending ? (
                          <Loader2 className="w-5 h-5 animate-spin text-augustus-400" />
                        ) : briefing.listened ? (
                          <Circle className="w-5 h-5 text-augustus-400" />
                        ) : (
                          <Check className="w-5 h-5 text-accent" />
                        )}
                        <div>
                          <span className="text-white font-medium block">
                            {briefing.listened ? 'Mark as unlistened' : 'Mark as listened'}
                          </span>
                          <span className="text-xs text-augustus-500">
                            {briefing.listened 
                              ? 'Remove from your listened history' 
                              : 'Add to your listened history'}
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
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-accent" />
            Transcript
            {segmentTimings.length > 0 && (
              <span className="text-xs font-normal text-augustus-400 ml-2">
                (click segments to jump to that part)
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
        <div className="card mt-6">
          <h2 className="text-lg font-semibold text-white mb-4">
            Sources ({briefing.sources.length})
          </h2>
          
          <div className="space-y-3">
            {briefing.sources.map((source, index) => (
              <a
                key={index}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-3 rounded-lg bg-augustus-900/50 hover:bg-augustus-800/50 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <ExternalLink className="w-4 h-4 text-augustus-500 flex-shrink-0 mt-0.5" />
                  <div>
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

