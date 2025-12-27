import { useRef, useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play, 
  Pause, 
  SkipBack, 
  SkipForward, 
  Volume2,
  VolumeX,
  X,
  ChevronUp,
  ChevronDown,
  Minimize2,
  Maximize2,
  Heart,
  Loader2
} from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store/useStore'
import { briefingsApi, castsApi } from '../api/client'

export default function AudioPlayer() {
  const navigate = useNavigate()
  const audioRef = useRef<HTMLAudioElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [showChapters, setShowChapters] = useState(false)
  const [hasMarkedListened, setHasMarkedListened] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [hasSetInitialPosition, setHasSetInitialPosition] = useState(false)
  const [hoveredChapterIndex, setHoveredChapterIndex] = useState<number | null>(null)
  // Audio player minimized state - persisted to localStorage
  const [isMinimized, setIsMinimized] = useState(() => {
    const saved = localStorage.getItem('audioPlayerMinimized')
    return saved !== null ? JSON.parse(saved) : false
  })
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
  
  // Fetch briefing to get cast_id
  const { data: briefing } = useQuery({
    queryKey: ['briefing', currentAudio?.id],
    queryFn: () => briefingsApi.get(currentAudio!.id),
    enabled: !!currentAudio?.id && currentAudio.type === 'briefing',
  })
  
  // Fetch cast information
  const { data: cast } = useQuery({
    queryKey: ['cast', briefing?.cast_id],
    queryFn: () => castsApi.get(briefing!.cast_id!),
    enabled: !!briefing?.cast_id,
  })
  
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
  
  // Mutation for updating favorite status
  const favoriteMutation = useMutation({
    mutationFn: ({ id, favorite }: { id: string; favorite: boolean }) => 
      briefingsApi.updateFavorite(id, favorite),
    onSuccess: () => {
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
  
  // Save minimized state to localStorage
  useEffect(() => {
    localStorage.setItem('audioPlayerMinimized', JSON.stringify(isMinimized))
  }, [isMinimized])
  
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
  
  // When audio source changes, pause old audio and load new source
  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !currentAudio) return
    
    // Pause any currently playing audio when switching to a new source
    audio.pause()
    
    // Load the new source (this will reset the audio element)
    audio.load()
    
    // Reset time tracking
    setCurrentTime(0)
    setHasSetInitialPosition(false)
  }, [currentAudio?.audioUrl, setCurrentTime])
  
  // Handle play/pause - ensure audio is ready before playing
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    
    if (isPlaying) {
      // Ensure audio is loaded before playing
      const playAudio = async () => {
        try {
          // If audio is not ready, wait for it
          if (audio.readyState < 2) {
            await new Promise((resolve) => {
              const handleCanPlay = () => {
                audio.removeEventListener('canplay', handleCanPlay)
                resolve(undefined)
              }
              audio.addEventListener('canplay', handleCanPlay)
            })
          }
          await audio.play()
        } catch (error) {
          // If play fails, reset playing state
          console.log('[AudioPlayer] Failed to play audio:', error)
          setIsPlaying(false)
        }
      }
      playAudio()
    } else {
      audio.pause()
    }
  }, [isPlaying, setIsPlaying])
  
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
  
  // Find the current active chapter
  const getActiveChapterIndex = useCallback((): number | null => {
    if (!currentAudio?.chapters || !duration) return null
    for (let i = 0; i < currentAudio.chapters.length; i++) {
      const chapter = currentAudio.chapters[i]
      if (currentTime >= chapter.start_time && 
          (chapter.end_time === undefined || currentTime < chapter.end_time)) {
        return i
      }
    }
    return null
  }, [currentAudio?.chapters, currentTime, duration])
  
  const activeChapterIndex = getActiveChapterIndex()
  
  // Handle chapter click
  const handleChapterClick = (chapterIndex: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!currentAudio?.chapters || !duration) return
    const chapter = currentAudio.chapters[chapterIndex]
    if (audioRef.current) {
      audioRef.current.currentTime = chapter.start_time
      setCurrentTime(chapter.start_time)
    }
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
  
  // Minimized view - compact player
  if (isMinimized) {
    return (
      <div className="px-2 py-2 sm:px-3 sm:py-3 md:p-4">
        <audio
          ref={audioRef}
          src={currentAudio.audioUrl}
          preload="metadata"
        />
        
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 sm:gap-2.5 md:gap-3">
            {/* Play/pause button */}
            <button
              onClick={handlePlayPause}
              className="w-10 h-10 sm:w-11 sm:h-11 md:w-12 md:h-12 aspect-square rounded-full bg-accent hover:bg-accent-600 text-white flex items-center justify-center flex-shrink-0 active:scale-95 transition-transform p-0"
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? (
                <Pause className="w-4 h-4 sm:w-5 sm:h-5 md:w-6 md:h-6" />
              ) : (
                <Play className="w-4 h-4 sm:w-5 sm:h-5 md:w-6 md:h-6 ml-0.5" />
              )}
            </button>
            
            {/* Track info */}
            <div className="flex-1 min-w-0">
              {currentAudio.type === 'briefing' && currentAudio.id ? (
                <button
                  onClick={() => navigate(`/briefing/${currentAudio.id}`)}
                  className="text-left w-full"
                >
                  <h4 className="font-medium text-white truncate text-sm sm:text-base hover:text-accent transition-colors cursor-pointer">
                    {currentAudio.title}
                  </h4>
                  <p className="text-xs text-augustus-500 mt-0.5 truncate">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </p>
                </button>
              ) : (
                <div>
                  <h4 className="font-medium text-white truncate text-sm sm:text-base">{currentAudio.title}</h4>
                  <p className="text-xs text-augustus-500 mt-0.5 truncate">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </p>
                </div>
              )}
            </div>
            
            {/* Favorite button - only show for briefings */}
            {currentAudio.type === 'briefing' && currentAudio.id && briefing && (
              <button
                onClick={() => favoriteMutation.mutate({ id: currentAudio.id, favorite: !briefing.favorite })}
                disabled={favoriteMutation.isPending}
                className={clsx(
                  'btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target transition-colors',
                  briefing.favorite
                    ? 'text-red-500 hover:text-red-400'
                    : 'text-augustus-400 hover:text-white'
                )}
                title={briefing.favorite ? 'Remove from favorites' : 'Add to favorites'}
                aria-label={briefing.favorite ? 'Remove from favorites' : 'Add to favorites'}
              >
                {favoriteMutation.isPending ? (
                  <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin" />
                ) : (
                  <Heart className={clsx('w-4 h-4 sm:w-5 sm:h-5', briefing.favorite && 'fill-current')} />
                )}
              </button>
            )}
            
            {/* Minimize/Expand button */}
            <button
              onClick={() => setIsMinimized(false)}
              className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target"
              title="Expand player"
              aria-label="Expand player"
            >
              <Maximize2 className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
            
            {/* Close button */}
            <button
              onClick={handleClose}
              className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target"
              title="Close player"
              aria-label="Close player"
            >
              <X className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
          </div>
          
          {/* Progress bar with timing - seekable */}
          <div 
            ref={progressRef}
            className="relative h-6 sm:h-8 flex items-center cursor-pointer touch-none -mx-1 px-1"
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
              {/* Chapter segments - show different colors for each chapter */}
              {currentAudio.chapters && currentAudio.chapters.length > 0 && duration && (
                <>
                  {currentAudio.chapters.map((chapter, index) => {
                    const startPercent = (chapter.start_time / duration) * 100
                    const endPercent = chapter.end_time 
                      ? (chapter.end_time / duration) * 100 
                      : 100
                    const width = endPercent - startPercent
                    const isActive = activeChapterIndex === index
                    
                    return (
                      <div
                        key={index}
                        className={clsx(
                          'absolute top-0 h-full rounded-full transition-all',
                          isActive 
                            ? 'bg-accent/60' 
                            : 'bg-augustus-700/50'
                        )}
                        style={{
                          left: `${startPercent}%`,
                          width: `${width}%`,
                        }}
                      />
                    )
                  })}
                </>
              )}
              
              {/* Progress fill */}
              <div 
                className="h-full bg-accent rounded-full transition-all duration-100 relative z-10"
                style={{ width: `${progress}%` }}
              />
              
              {/* Chapter markers */}
              {currentAudio.chapters && currentAudio.chapters.length > 0 && duration && (
                <>
                  {currentAudio.chapters.map((chapter, index) => {
                    const position = (chapter.start_time / duration) * 100
                    const isActive = activeChapterIndex === index
                    const isHovered = hoveredChapterIndex === index
                    
                    return (
                      <div
                        key={index}
                        className={clsx(
                          'absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-20',
                          'transition-all duration-200'
                        )}
                        style={{ left: `${position}%` }}
                        onMouseEnter={() => setHoveredChapterIndex(index)}
                        onMouseLeave={() => setHoveredChapterIndex(null)}
                        onClick={(e) => handleChapterClick(index, e)}
                      >
                        {/* Chapter marker line */}
                        <div
                          className={clsx(
                            'w-0.5 h-3 sm:h-4 transition-all',
                            isActive 
                              ? 'bg-accent shadow-lg shadow-accent/50' 
                              : isHovered
                              ? 'bg-augustus-300'
                              : 'bg-augustus-600'
                          )}
                        />
                        
                        {/* Chapter tooltip on hover */}
                        {isHovered && (
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-augustus-900 border border-augustus-700 rounded text-xs text-white whitespace-nowrap shadow-lg z-30">
                            <div className="font-medium">{chapter.title}</div>
                            <div className="text-augustus-400 text-[10px] mt-0.5">
                              {formatTime(chapter.start_time)}
                            </div>
                            {/* Tooltip arrow */}
                            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px">
                              <div className="w-2 h-2 bg-augustus-900 border-r border-b border-augustus-700 rotate-45"></div>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </>
              )}
              
              {/* Thumb indicator */}
              <div 
                className={clsx(
                  'absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 sm:w-3 sm:h-3 bg-white rounded-full shadow-lg transition-transform touch-none z-30',
                  isDragging && 'scale-125'
                )}
                style={{ left: `${progress}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    )
  }
  
  // Full expanded view
  return (
    <div className="px-2 py-2 sm:px-3 sm:py-3 md:p-4">
      <audio
        ref={audioRef}
        src={currentAudio.audioUrl}
        preload="metadata"
      />
      
      {/* Chapters panel - replaces transcript when chapters are available */}
      {showChapters && currentAudio.chapters && currentAudio.chapters.length > 0 && (
        <div className="mb-2 sm:mb-3 max-h-32 sm:max-h-40 md:max-h-48 overflow-auto bg-augustus-950/50 rounded-lg p-2 sm:p-3 md:p-4">
          <div className="space-y-1 sm:space-y-2">
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
                    'w-full text-left p-1.5 sm:p-2 md:p-3 rounded-lg transition-all duration-200 active:scale-[0.98] min-h-[44px] sm:min-h-[36px]',
                    isActive
                      ? 'bg-accent/25 ring-1 ring-accent text-white'
                      : 'bg-augustus-900/50 hover:bg-augustus-800/50 text-augustus-200'
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={clsx(
                      'text-xs sm:text-sm font-medium truncate flex-1',
                      isActive ? 'text-white' : 'text-augustus-200'
                    )}>
                      {chapter.title}
                    </span>
                    <span className={clsx(
                      'text-xs font-mono flex-shrink-0',
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
        <div className="mb-2 sm:mb-3 max-h-32 sm:max-h-40 md:max-h-48 overflow-auto bg-augustus-950/50 rounded-lg p-2 sm:p-3 md:p-4 text-augustus-300">
          <pre className="whitespace-pre-wrap font-sans text-xs sm:text-sm">{currentAudio.transcript}</pre>
        </div>
      )}
      
      {/* Mobile-first compact layout */}
      <div className="flex flex-col gap-2 sm:gap-2.5 md:gap-3">
        {/* Top row: Track info + main controls */}
        <div className="flex items-center gap-2 sm:gap-2.5 md:gap-3">
          {/* Play/pause button - large touch target */}
          <button
            onClick={handlePlayPause}
            className="w-11 h-11 sm:w-12 sm:h-12 md:w-14 md:h-14 aspect-square rounded-full bg-accent hover:bg-accent-600 text-white flex items-center justify-center flex-shrink-0 active:scale-95 transition-transform p-0"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <Pause className="w-5 h-5 sm:w-6 sm:h-6 md:w-7 md:h-7" />
            ) : (
              <Play className="w-5 h-5 sm:w-6 sm:h-6 md:w-7 md:h-7 ml-0.5" />
            )}
          </button>
          
          {/* Track info */}
          <div className="flex-1 min-w-0">
            {currentAudio.type === 'briefing' && currentAudio.id ? (
              <button
                onClick={() => navigate(`/briefing/${currentAudio.id}`)}
                className="text-left w-full min-h-[44px] sm:min-h-0 flex flex-col justify-center"
              >
                <h4 className="font-medium text-white truncate text-sm sm:text-base hover:text-accent transition-colors cursor-pointer">
                  {currentAudio.title}
                </h4>
                <p className="text-xs text-augustus-500 mt-0.5 truncate">
                  {currentAudio.chapters && currentAudio.chapters.length > 0 && activeChapterIndex !== null
                    ? currentAudio.chapters[activeChapterIndex].title
                    : cast?.name || currentAudio.type}
                </p>
              </button>
            ) : (
              <div className="min-h-[44px] sm:min-h-0 flex flex-col justify-center">
                <h4 className="font-medium text-white truncate text-sm sm:text-base">{currentAudio.title}</h4>
                <p className="text-xs text-augustus-500 mt-0.5 truncate">
                  {currentAudio.chapters && currentAudio.chapters.length > 0 && activeChapterIndex !== null
                    ? currentAudio.chapters[activeChapterIndex].title
                    : cast?.name || currentAudio.type}
                </p>
              </div>
            )}
          </div>
          
          {/* Skip controls - compact on mobile */}
          <div className="flex items-center gap-0.5 sm:gap-1">
            <button
              onClick={() => skip(-15)}
              className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target"
              title="Back 15s"
              aria-label="Back 15 seconds"
            >
              <SkipBack className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
            <button
              onClick={() => skip(30)}
              className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target"
              title="Forward 30s"
              aria-label="Forward 30 seconds"
            >
              <SkipForward className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
          </div>
          
          {/* Favorite button - only show for briefings */}
          {currentAudio.type === 'briefing' && currentAudio.id && briefing && (
            <button
              onClick={() => favoriteMutation.mutate({ id: currentAudio.id, favorite: !briefing.favorite })}
              disabled={favoriteMutation.isPending}
              className={clsx(
                'btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target transition-colors',
                briefing.favorite
                  ? 'text-red-500 hover:text-red-400'
                  : 'text-augustus-400 hover:text-white'
              )}
              title={briefing.favorite ? 'Remove from favorites' : 'Add to favorites'}
              aria-label={briefing.favorite ? 'Remove from favorites' : 'Add to favorites'}
            >
              {favoriteMutation.isPending ? (
                <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin" />
              ) : (
                <Heart className={clsx('w-4 h-4 sm:w-5 sm:h-5', briefing.favorite && 'fill-current')} />
              )}
            </button>
          )}
          
          {/* Minimize button */}
          <button
            onClick={() => setIsMinimized(true)}
            className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target"
            title="Minimize player"
            aria-label="Minimize player"
          >
            <Minimize2 className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
          
          {/* Close button */}
          <button
            onClick={handleClose}
            className="btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target"
            title="Close player"
            aria-label="Close player"
          >
            <X className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
        </div>
        
        {/* Progress bar - touch-optimized */}
        <div 
          ref={progressRef}
          className="relative h-8 sm:h-10 flex items-center cursor-pointer touch-none -mx-1 px-1"
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
          <div className="absolute inset-x-0 h-2.5 sm:h-2 bg-augustus-800 rounded-full">
            {/* Chapter segments - show different colors for each chapter */}
            {currentAudio.chapters && currentAudio.chapters.length > 0 && duration && (
              <>
                {currentAudio.chapters.map((chapter, index) => {
                  const startPercent = (chapter.start_time / duration) * 100
                  const endPercent = chapter.end_time 
                    ? (chapter.end_time / duration) * 100 
                    : 100
                  const width = endPercent - startPercent
                  const isActive = activeChapterIndex === index
                  
                  return (
                    <div
                      key={index}
                      className={clsx(
                        'absolute top-0 h-full rounded-full transition-all',
                        isActive 
                          ? 'bg-accent/60' 
                          : 'bg-augustus-700/50'
                      )}
                      style={{
                        left: `${startPercent}%`,
                        width: `${width}%`,
                      }}
                    />
                  )
                })}
              </>
            )}
            
            {/* Progress fill */}
            <div 
              className="h-full bg-accent rounded-full transition-all duration-100 relative z-10"
              style={{ width: `${progress}%` }}
            />
            
            {/* Chapter markers */}
            {currentAudio.chapters && currentAudio.chapters.length > 0 && duration && (
              <>
                {currentAudio.chapters.map((chapter, index) => {
                  const position = (chapter.start_time / duration) * 100
                  const isActive = activeChapterIndex === index
                  const isHovered = hoveredChapterIndex === index
                  
                  return (
                    <div
                      key={index}
                      className={clsx(
                        'absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-20',
                        'transition-all duration-200'
                      )}
                      style={{ left: `${position}%` }}
                      onMouseEnter={() => setHoveredChapterIndex(index)}
                      onMouseLeave={() => setHoveredChapterIndex(null)}
                      onClick={(e) => handleChapterClick(index, e)}
                    >
                      {/* Chapter marker line */}
                      <div
                        className={clsx(
                          'w-0.5 h-4 sm:h-5 transition-all',
                          isActive 
                            ? 'bg-accent shadow-lg shadow-accent/50' 
                            : isHovered
                            ? 'bg-augustus-300'
                            : 'bg-augustus-600'
                        )}
                      />
                      
                      {/* Chapter tooltip on hover */}
                      {isHovered && (
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-augustus-900 border border-augustus-700 rounded text-xs text-white whitespace-nowrap shadow-lg z-30">
                          <div className="font-medium">{chapter.title}</div>
                          <div className="text-augustus-400 text-[10px] mt-0.5">
                            {formatTime(chapter.start_time)}
                          </div>
                          {/* Tooltip arrow */}
                          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px">
                            <div className="w-2 h-2 bg-augustus-900 border-r border-b border-augustus-700 rotate-45"></div>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </>
            )}
            
            {/* Thumb indicator - larger on mobile for easier dragging */}
            <div 
              className={clsx(
                'absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-5 h-5 sm:w-4 sm:h-4 bg-white rounded-full shadow-lg transition-transform touch-none z-30',
                isDragging && 'scale-125'
              )}
              style={{ left: `${progress}%` }}
            />
          </div>
        </div>
        
        {/* Bottom row: Time + additional controls */}
        <div className="flex items-center justify-between gap-2">
          {/* Time display */}
          <div className="flex items-center gap-1 sm:gap-2 text-xs font-mono text-augustus-500">
            <span>{formatTime(currentTime)}</span>
            <span className="text-augustus-600">/</span>
            <span>{formatTime(duration)}</span>
          </div>
          
          {/* Additional controls */}
          <div className="flex items-center gap-1 sm:gap-2">
            {/* Speed button */}
            <button
              onClick={cyclePlaybackRate}
              className="btn btn-ghost px-2 py-1.5 sm:px-3 sm:py-1 text-xs sm:text-sm font-mono min-h-[44px] sm:min-h-[36px] touch-target"
              title="Playback speed"
              aria-label={`Playback speed: ${playbackRate}x`}
            >
              {playbackRate}x
            </button>
            
            {/* Volume - hidden on mobile (use device volume) */}
            <div className="hidden sm:flex items-center gap-2">
              <button
                onClick={() => setIsMuted(!isMuted)}
                className="btn-icon btn btn-ghost p-2"
                aria-label={isMuted ? 'Unmute' : 'Mute'}
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
                aria-label="Volume"
              />
            </div>
            
            {/* Chapters/Transcript toggle */}
            {(currentAudio.chapters && currentAudio.chapters.length > 0) || currentAudio.transcript ? (
              <button
                onClick={() => setShowChapters(!showChapters)}
                className={clsx(
                  'btn-icon btn btn-ghost p-1.5 sm:p-2 min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] touch-target',
                  showChapters && 'text-accent'
                )}
                title={currentAudio.chapters && currentAudio.chapters.length > 0 ? "Toggle chapters" : "Toggle transcript"}
                aria-label={showChapters ? 'Hide chapters' : 'Show chapters'}
              >
                {showChapters ? (
                  <ChevronDown className="w-4 h-4 sm:w-5 sm:h-5" />
                ) : (
                  <ChevronUp className="w-4 h-4 sm:w-5 sm:h-5" />
                )}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
