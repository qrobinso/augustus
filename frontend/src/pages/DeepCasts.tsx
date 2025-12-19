import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play, 
  Loader2, 
  Search, 
  Clock, 
  Calendar,
  Trash2,
  AlertCircle,
  ExternalLink,
  Mic2
} from 'lucide-react'
import clsx from 'clsx'
import { deepcastsApi, castsApi, DeepCast } from '../api/client'
import { useStore } from '../store/useStore'

export default function DeepCasts() {
  const queryClient = useQueryClient()
  const setCurrentAudio = useStore((s) => s.setCurrentAudio)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  
  const [query, setQuery] = useState('')
  const [duration, setDuration] = useState(10)
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(undefined)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['deepcasts'],
    queryFn: () => deepcastsApi.list(),
    refetchInterval: 10000,
  })
  
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  const createMutation = useMutation({
    mutationFn: () => deepcastsApi.create({
      query,
      target_duration_minutes: duration,
      cast_id: selectedCastId,
    }),
    onSuccess: () => {
      setQuery('')
      queryClient.invalidateQueries({ queryKey: ['deepcasts'] })
    },
  })
  
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deepcastsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deepcasts'] })
    },
  })
  
  const handlePlay = (deepcast: DeepCast) => {
    if (deepcast.audio_url) {
      setCurrentAudio({
        id: deepcast.id,
        type: 'deepcast',
        title: deepcast.title || deepcast.query,
        audioUrl: deepcast.audio_url,
        transcript: deepcast.transcript,
        chapters: deepcast.chapters,
      })
      setIsPlaying(true)
    }
  }
  
  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      createMutation.mutate()
    }
  }
  
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--:--'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }
  
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  }
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          DeepCasts
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          On-demand podcasts generated from any topic or question
        </p>
      </div>
      
      {/* Create new DeepCast */}
      <form onSubmit={handleCreate} className="card mb-6 sm:mb-8">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Mic2 className="w-5 h-5 text-accent" />
          Create New DeepCast
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="label">Topic or Question</label>
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-augustus-500" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., How does quantum computing work?"
                className="input pl-12"
              />
            </div>
          </div>
          
          <div>
            <label className="label">Target Duration</label>
            <div className="flex items-center gap-2 sm:gap-4 overflow-x-auto pb-1">
              {[5, 10, 15, 20].map((mins) => (
                <button
                  key={mins}
                  type="button"
                  onClick={() => setDuration(mins)}
                  className={clsx(
                    'px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap min-h-[40px]',
                    duration === mins
                      ? 'bg-accent text-white'
                      : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                  )}
                >
                  {mins} min
                </button>
              ))}
            </div>
          </div>
          
          {/* Cast selector */}
          {castsData && castsData.casts.length > 1 && (
            <div>
              <label className="label">Cast</label>
              <select
                value={selectedCastId || castsData.casts.find(c => c.is_default)?.id || ''}
                onChange={(e) => setSelectedCastId(e.target.value || undefined)}
                className="input"
              >
                {castsData.casts.map((cast) => (
                  <option key={cast.id} value={cast.id}>
                    {cast.name}{cast.is_default ? ' ★' : ''}
                  </option>
                ))}
              </select>
            </div>
          )}
          
          <button
            type="submit"
            disabled={!query.trim() || createMutation.isPending}
            className="btn btn-primary w-full sm:w-auto flex items-center justify-center gap-2"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Mic2 className="w-5 h-5" />
                Create DeepCast
              </>
            )}
          </button>
        </div>
      </form>
      
      {/* DeepCasts list */}
      <div className="space-y-3 sm:space-y-4">
        {isLoading ? (
          <div className="card flex items-center justify-center py-10 sm:py-12">
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="card text-center py-10 sm:py-12">
            <AlertCircle className="w-10 sm:w-12 h-10 sm:h-12 text-red-500 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">Failed to load DeepCasts. Is the backend running?</p>
          </div>
        ) : data?.deepcasts.length === 0 ? (
          <div className="card text-center py-10 sm:py-12">
            <Mic2 className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">No DeepCasts yet. Create your first one!</p>
          </div>
        ) : (
          data?.deepcasts.map((deepcast) => (
            <div
              key={deepcast.id}
              className="card hover:border-augustus-700 transition-colors"
            >
              <div className="flex items-start gap-3 sm:gap-4">
                {/* Play button */}
                <button
                  onClick={() => handlePlay(deepcast)}
                  disabled={deepcast.status !== 'completed'}
                  className={clsx(
                    'w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center flex-shrink-0 transition-all',
                    deepcast.status === 'completed'
                      ? 'bg-accent hover:bg-accent-600 text-white glow active:scale-95'
                      : 'bg-augustus-800 text-augustus-500'
                  )}
                >
                  {['generating', 'researching', 'pending'].includes(deepcast.status) ? (
                    <Loader2 className="w-5 h-5 sm:w-6 sm:h-6 animate-spin" />
                  ) : deepcast.status === 'failed' ? (
                    <AlertCircle className="w-5 h-5 sm:w-6 sm:h-6 text-red-500" />
                  ) : (
                    <Play className="w-5 h-5 sm:w-6 sm:h-6 ml-0.5 sm:ml-1" />
                  )}
                </button>
                
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-white text-sm sm:text-base">
                    {deepcast.title || deepcast.query}
                  </h3>
                  {deepcast.title && (
                    <p className="text-xs sm:text-sm text-augustus-400 truncate">{deepcast.query}</p>
                  )}
                  <div className="flex flex-wrap items-center gap-x-3 sm:gap-x-4 gap-y-1 text-xs sm:text-sm text-augustus-500 mt-1.5 sm:mt-2">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      {formatDuration(deepcast.duration_seconds)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      {formatDate(deepcast.created_at)}
                    </span>
                    <span className={clsx(
                      'px-1.5 sm:px-2 py-0.5 rounded-full text-xs font-medium',
                      deepcast.status === 'completed' && 'bg-green-500/20 text-green-400',
                      deepcast.status === 'generating' && 'bg-yellow-500/20 text-yellow-400',
                      deepcast.status === 'researching' && 'bg-blue-500/20 text-blue-400',
                      deepcast.status === 'pending' && 'bg-augustus-700 text-augustus-400',
                      deepcast.status === 'failed' && 'bg-red-500/20 text-red-400',
                    )}>
                      {deepcast.status}
                    </span>
                  </div>
                  
                  {/* Sources - show fewer on mobile */}
                  {deepcast.sources.length > 0 && (
                    <div className="mt-2 sm:mt-3 flex flex-wrap gap-1.5 sm:gap-2">
                      {deepcast.sources.slice(0, 2).map((source, i) => (
                        <a
                          key={i}
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-augustus-400 
                                     hover:text-accent bg-augustus-800/50 px-2 py-1 rounded active:bg-augustus-700"
                        >
                          <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          <span className="truncate max-w-[150px] sm:max-w-[200px]">{source.title}</span>
                        </a>
                      ))}
                      {deepcast.sources.length > 2 && (
                        <span className="text-xs text-augustus-500 px-2 py-1">
                          +{deepcast.sources.length - 2} more
                        </span>
                      )}
                    </div>
                  )}
                  
                  {deepcast.error_message && (
                    <p className="text-xs sm:text-sm text-red-400 mt-2">{deepcast.error_message}</p>
                  )}
                </div>
                
                {/* Actions */}
                <button
                  onClick={() => deleteMutation.mutate(deepcast.id)}
                  className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400 flex-shrink-0"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
