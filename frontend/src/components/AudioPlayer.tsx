import { useRef, useEffect, useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play, 
  Pause, 
  SkipBack, 
  SkipForward, 
  Volume2,
  VolumeX,
  X,
  ChevronUp,
  ChevronDown
} from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store/useStore'
import { briefingsApi } from '../api/client'

export default function AudioPlayer() {
  const audioRef = useRef<HTMLAudioElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [showChapters, setShowChapters] = useState(false)
  const [hasMarkedListened, setHasMarkedListened] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [hasSetInitialPosition, setHasSetInitialPosition] = useState(false)
  const lastSavedPositionRef = useRef<number>(0)
  const queryClient = useQueryClient()
  
  const { 
    currentAudio, 
    isPlaying, 
    currentTime, 
    duration,
    setIsPlaying,
    setCurrentTime,
    setDuration,
    clearAudio,
  } = useStore()
  
  // Mutation for marking as listened
  const markListenedMutation = useMutation({
    mutationFn: (id: string) => briefingsApi.updateListened(id, true),
    onSuccess: () => {
      // Invalidate all briefings queries (with any filter/page combination)
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
      if (currentAudio?.id) {
        queryClient.invalidateQueries({ queryKey: ['briefing', currentAudio.id] })
      }
    },
  })
  
  // Mutation for saving playback position
  const savePositionMutation = useMutation({
    mutationFn: ({ id, position }: { id: string; position: number }) => 
      briefingsApi.updatePlaybackPosition(id, position),
  })
  
  // Save playback position (debounced to avoid too many API calls)
  const savePlaybackPosition = useCallback((position: number) => {
    if (currentAudio?.type === 'briefing' && currentAudio.id) {
      // Only save if position has changed by more than 5 seconds
      if (Math.abs(position - lastSavedPositionRef.current) >= 5) {
        lastSavedPositionRef.current = position
        savePositionMutation.mutate({ id: currentAudio.id, position })
      }
    }
  }, [currentAudio, savePositionMutation])
  
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    
    const handleTimeUpdate = () => {
      const newTime = audio.currentTime
      setCurrentTime(newTime)
      
      // Auto-mark as listened if played for more than 5 seconds
      if (
        currentAudio?.type === 'briefing' &&
        currentAudio.id &&
        !hasMarkedListened &&
        newTime >= 5
      ) {
        setHasMarkedListened(true)
        markListenedMutation.mutate(currentAudio.id)
      }
      
      // Save playback position every 10 seconds of playback
      if (currentAudio?.type === 'briefing' && Math.floor(newTime) % 10 === 0) {
        savePlaybackPosition(newTime)
      }
    }
    
    const handleDurationChange = () => setDuration(audio.duration)
    const handleEnded = () => {
      setIsPlaying(false)
      // Reset position to 0 when audio ends (fully listened)
      if (currentAudio?.type === 'briefing' && currentAudio.id) {
        savePositionMutation.mutate({ id: currentAudio.id, position: 0 })
        lastSavedPositionRef.current = 0
      }
    }
    
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('durationchange', handleDurationChange)
    audio.addEventListener('ended', handleEnded)
    
    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('durationchange', handleDurationChange)
      audio.removeEventListener('ended', handleEnded)
    }
  }, [setCurrentTime, setDuration, setIsPlaying, currentAudio, hasMarkedListened, markListenedMutation, savePlaybackPosition, savePositionMutation])
  
  // Reset state when audio changes
  useEffect(() => {
    setHasMarkedListened(false)
    setHasSetInitialPosition(false)
    lastSavedPositionRef.current = currentAudio?.initialPosition || 0
  }, [currentAudio?.id, currentAudio?.initialPosition])
  
  // Seek to initial position when audio is loaded
  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !currentAudio?.initialPosition || hasSetInitialPosition) return
    
    const handleCanPlay = () => {
      if (currentAudio.initialPosition && currentAudio.initialPosition > 0) {
        audio.currentTime = currentAudio.initialPosition
        setCurrentTime(currentAudio.initialPosition)
        setHasSetInitialPosition(true)
      }
    }
    
    // If audio is already loaded, seek immediately
    if (audio.readyState >= 3) {
      handleCanPlay()
    } else {
      audio.addEventListener('canplay', handleCanPlay)
      return () => audio.removeEventListener('canplay', handleCanPlay)
    }
  }, [currentAudio?.initialPosition, currentAudio?.id, hasSetInitialPosition, setCurrentTime])
  
  useEffect(() => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.play()
      } else {
        audioRef.current.pause()
      }
    }
  }, [isPlaying])
  
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume
    }
  }, [volume, isMuted])
  
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate
    }
  }, [playbackRate])
  
  const formatTime = (seconds: number) => {
    if (!seconds || isNaN(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }
  
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value)
    if (audioRef.current) {
      audioRef.current.currentTime = time
    }
    setCurrentTime(time)
  }
  
  // Touch-friendly seek handling
  const handleProgressTouch = (e: React.TouchEvent | React.MouseEvent) => {
    if (!progressRef.current || !duration) return
    
    const rect = progressRef.current.getBoundingClientRect()
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    const time = percent * duration
    
    if (audioRef.current) {
      audioRef.current.currentTime = time
    }
    setCurrentTime(time)
  }
  
  const skip = (seconds: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, Math.min(duration, currentTime + seconds))
    }
  }
  
  const cyclePlaybackRate = () => {
    const rates = [0.75, 1, 1.25, 1.5, 1.75, 2]
    const currentIndex = rates.indexOf(playbackRate)
    const nextIndex = (currentIndex + 1) % rates.length
    setPlaybackRate(rates[nextIndex])
  }
  
  // Handle close: save position before clearing
  const handleClose = () => {
    if (currentAudio?.type === 'briefing' && currentAudio.id && currentTime > 0) {
      // Save current position before closing
      savePositionMutation.mutate({ id: currentAudio.id, position: currentTime })
    }
    clearAudio()
  }
  
  // Handle play/pause: save position on pause
  const handlePlayPause = () => {
    if (isPlaying && currentAudio?.type === 'briefing' && currentAudio.id) {
      // Save position when pausing
      savePlaybackPosition(currentTime)
    }
    setIsPlaying(!isPlaying)
  }
  
  if (!currentAudio) return null
  
  const progress = duration ? (currentTime / duration) * 100 : 0
  
  return (
    <div className="p-3 sm:p-4">
      <audio
        ref={audioRef}
        src={currentAudio.audioUrl}
        preload="metadata"
      />
      
      {/* Chapters panel - replaces transcript when chapters are available */}
      {showChapters && currentAudio.chapters && currentAudio.chapters.length > 0 && (
        <div className="mb-3 max-h-40 sm:max-h-48 overflow-auto bg-augustus-950/50 rounded-lg p-3 sm:p-4">
          <div className="space-y-2">
            {currentAudio.chapters.map((chapter, index) => {
              // Find active chapter based on current time
              const isActive = currentTime >= chapter.start_time && 
                               (chapter.end_time === undefined || currentTime < chapter.end_time)
              
              return (
                <button
                  key={index}
                  onClick={() => {
                    if (audioRef.current) {
                      audioRef.current.currentTime = chapter.start_time
                      setCurrentTime(chapter.start_time)
                    }
                  }}
                  className={clsx(
                    'w-full text-left p-2 sm:p-3 rounded-lg transition-all duration-200 active:scale-[0.98]',
                    isActive
                      ? 'bg-accent/25 ring-1 ring-accent text-white'
                      : 'bg-augustus-900/50 hover:bg-augustus-800/50 text-augustus-200'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className={clsx(
                      'text-xs sm:text-sm font-medium',
                      isActive ? 'text-white' : 'text-augustus-200'
                    )}>
                      {chapter.title}
                    </span>
                    <span className={clsx(
                      'text-xs font-mono ml-2',
                      isActive ? 'text-accent' : 'text-augustus-500'
                    )}>
                      {formatTime(chapter.start_time)}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
      
      {/* Transcript panel - fallback when no chapters */}
      {showChapters && (!currentAudio.chapters || currentAudio.chapters.length === 0) && currentAudio.transcript && (
        <div className="mb-3 max-h-40 sm:max-h-48 overflow-auto bg-augustus-950/50 rounded-lg p-3 sm:p-4 text-sm text-augustus-300">
          <pre className="whitespace-pre-wrap font-sans text-xs sm:text-sm">{currentAudio.transcript}</pre>
        </div>
      )}
      
      {/* Mobile-first compact layout */}
      <div className="flex flex-col gap-3">
        {/* Top row: Track info + main controls */}
        <div className="flex items-center gap-3">
          {/* Play/pause button - large touch target */}
          <button
            onClick={handlePlayPause}
            className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-accent hover:bg-accent-600 text-white flex items-center justify-center flex-shrink-0 active:scale-95 transition-transform"
          >
            {isPlaying ? (
              <Pause className="w-6 h-6 sm:w-7 sm:h-7" />
            ) : (
              <Play className="w-6 h-6 sm:w-7 sm:h-7 ml-0.5" />
            )}
          </button>
          
          {/* Track info */}
          <div className="flex-1 min-w-0">
            <h4 className="font-medium text-white truncate text-sm sm:text-base">{currentAudio.title}</h4>
            <p className="text-xs sm:text-sm text-augustus-500 capitalize">{currentAudio.type}</p>
          </div>
          
          {/* Skip controls - visible on larger screens or always on mobile */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => skip(-15)}
              className="btn-icon btn btn-ghost p-2"
              title="Back 15s"
            >
              <SkipBack className="w-5 h-5" />
            </button>
            <button
              onClick={() => skip(30)}
              className="btn-icon btn btn-ghost p-2"
              title="Forward 30s"
            >
              <SkipForward className="w-5 h-5" />
            </button>
          </div>
          
          {/* Close button */}
          <button
            onClick={handleClose}
            className="btn-icon btn btn-ghost p-2"
            title="Close player"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Progress bar - touch-optimized */}
        <div 
          ref={progressRef}
          className="relative h-10 flex items-center cursor-pointer touch-none"
          onClick={handleProgressTouch}
          onTouchStart={(e) => {
            setIsDragging(true)
            handleProgressTouch(e)
          }}
          onTouchMove={(e) => {
            if (isDragging) handleProgressTouch(e)
          }}
          onTouchEnd={() => setIsDragging(false)}
        >
          {/* Background track */}
          <div className="absolute inset-x-0 h-2 bg-augustus-800 rounded-full">
            {/* Progress fill */}
            <div 
              className="h-full bg-accent rounded-full transition-all duration-100"
              style={{ width: `${progress}%` }}
            />
            {/* Thumb indicator */}
            <div 
              className={clsx(
                'absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg transition-transform',
                isDragging && 'scale-125'
              )}
              style={{ left: `calc(${progress}% - 8px)` }}
            />
          </div>
        </div>
        
        {/* Bottom row: Time + additional controls */}
        <div className="flex items-center justify-between">
          {/* Time display */}
          <div className="flex items-center gap-2 text-xs sm:text-sm font-mono text-augustus-500">
            <span>{formatTime(currentTime)}</span>
            <span>/</span>
            <span>{formatTime(duration)}</span>
          </div>
          
          {/* Additional controls */}
          <div className="flex items-center gap-1 sm:gap-2">
            {/* Speed button */}
            <button
              onClick={cyclePlaybackRate}
              className="btn btn-ghost px-2 sm:px-3 py-1 text-xs sm:text-sm font-mono min-h-[36px]"
              title="Playback speed"
            >
              {playbackRate}x
            </button>
            
            {/* Volume - hidden on mobile (use device volume) */}
            <div className="hidden sm:flex items-center gap-2">
              <button
                onClick={() => setIsMuted(!isMuted)}
                className="btn-icon btn btn-ghost p-2"
              >
                {isMuted ? (
                  <VolumeX className="w-5 h-5" />
                ) : (
                  <Volume2 className="w-5 h-5" />
                )}
              </button>
              
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={isMuted ? 0 : volume}
                onChange={(e) => {
                  setVolume(parseFloat(e.target.value))
                  setIsMuted(false)
                }}
                className="w-20 h-1 bg-augustus-800 rounded-full appearance-none cursor-pointer
                           [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 
                           [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-augustus-300 
                           [&::-webkit-slider-thumb]:rounded-full"
              />
            </div>
            
            {/* Chapters/Transcript toggle */}
            {(currentAudio.chapters && currentAudio.chapters.length > 0) || currentAudio.transcript ? (
              <button
                onClick={() => setShowChapters(!showChapters)}
                className={clsx(
                  'btn-icon btn btn-ghost p-2',
                  showChapters && 'text-accent'
                )}
                title={currentAudio.chapters && currentAudio.chapters.length > 0 ? "Toggle chapters" : "Toggle transcript"}
              >
                {showChapters ? (
                  <ChevronDown className="w-5 h-5" />
                ) : (
                  <ChevronUp className="w-5 h-5" />
                )}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
