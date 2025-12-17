import { useRef, useEffect, useState } from 'react'
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
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [showTranscript, setShowTranscript] = useState(false)
  const [hasMarkedListened, setHasMarkedListened] = useState(false)
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
    }
    
    const handleDurationChange = () => setDuration(audio.duration)
    const handleEnded = () => setIsPlaying(false)
    
    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('durationchange', handleDurationChange)
    audio.addEventListener('ended', handleEnded)
    
    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('durationchange', handleDurationChange)
      audio.removeEventListener('ended', handleEnded)
    }
  }, [setCurrentTime, setDuration, setIsPlaying, currentAudio, hasMarkedListened, markListenedMutation])
  
  // Reset hasMarkedListened when audio changes
  useEffect(() => {
    setHasMarkedListened(false)
  }, [currentAudio?.id])
  
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
  
  if (!currentAudio) return null
  
  return (
    <div className="p-4">
      <audio
        ref={audioRef}
        src={currentAudio.audioUrl}
        preload="metadata"
      />
      
      {/* Transcript panel */}
      {showTranscript && currentAudio.transcript && (
        <div className="mb-4 max-h-48 overflow-auto bg-augustus-950/50 rounded-lg p-4 text-sm text-augustus-300">
          <pre className="whitespace-pre-wrap font-sans">{currentAudio.transcript}</pre>
        </div>
      )}
      
      <div className="flex items-center gap-4">
        {/* Track info */}
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-white truncate">{currentAudio.title}</h4>
          <p className="text-sm text-augustus-500 capitalize">{currentAudio.type}</p>
        </div>
        
        {/* Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => skip(-15)}
            className="btn btn-ghost p-2"
            title="Back 15s"
          >
            <SkipBack className="w-5 h-5" />
          </button>
          
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn btn-primary p-3 rounded-full"
          >
            {isPlaying ? (
              <Pause className="w-6 h-6" />
            ) : (
              <Play className="w-6 h-6 ml-0.5" />
            )}
          </button>
          
          <button
            onClick={() => skip(30)}
            className="btn btn-ghost p-2"
            title="Forward 30s"
          >
            <SkipForward className="w-5 h-5" />
          </button>
        </div>
        
        {/* Progress */}
        <div className="flex-1 flex items-center gap-3">
          <span className="text-sm text-augustus-500 w-12 text-right font-mono">
            {formatTime(currentTime)}
          </span>
          
          <input
            type="range"
            min={0}
            max={duration || 100}
            value={currentTime}
            onChange={handleSeek}
            className="flex-1 h-2 bg-augustus-800 rounded-full appearance-none cursor-pointer
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 
                       [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-accent 
                       [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                       [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-accent/30"
          />
          
          <span className="text-sm text-augustus-500 w-12 font-mono">
            {formatTime(duration)}
          </span>
        </div>
        
        {/* Speed */}
        <button
          onClick={cyclePlaybackRate}
          className="btn btn-ghost px-3 py-1 text-sm font-mono"
          title="Playback speed"
        >
          {playbackRate}x
        </button>
        
        {/* Volume */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsMuted(!isMuted)}
            className="btn btn-ghost p-2"
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
        
        {/* Transcript toggle */}
        {currentAudio.transcript && (
          <button
            onClick={() => setShowTranscript(!showTranscript)}
            className={clsx(
              'btn btn-ghost p-2',
              showTranscript && 'text-accent'
            )}
            title="Toggle transcript"
          >
            {showTranscript ? (
              <ChevronDown className="w-5 h-5" />
            ) : (
              <ChevronUp className="w-5 h-5" />
            )}
          </button>
        )}
        
        {/* Close */}
        <button
          onClick={clearAudio}
          className="btn btn-ghost p-2"
          title="Close player"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}

