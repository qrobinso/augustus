import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play, 
  Loader2, 
  Radio, 
  Clock, 
  Calendar,
  Trash2,
  AlertCircle,
  Plus,
  RefreshCw,
  Pause,
  ChevronDown,
  ChevronUp
} from 'lucide-react'
import clsx from 'clsx'
import { stationsApi, castsApi, Station, Episode } from '../api/client'
import { useStore } from '../store/useStore'

export default function Stations() {
  const queryClient = useQueryClient()
  const setCurrentAudio = useStore((s) => s.setCurrentAudio)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  
  const [topic, setTopic] = useState('')
  const [description, setDescription] = useState('')
  const [frequency, setFrequency] = useState(6)
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(undefined)
  const [expandedStation, setExpandedStation] = useState<string | null>(null)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['stations'],
    queryFn: () => stationsApi.list(),
    refetchInterval: 10000,
  })
  
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  const createMutation = useMutation({
    mutationFn: () => stationsApi.create({
      topic,
      description: description || undefined,
      update_frequency_hours: frequency,
      cast_id: selectedCastId,
    }),
    onSuccess: () => {
      setTopic('')
      setDescription('')
      setSelectedCastId(undefined)
      queryClient.invalidateQueries({ queryKey: ['stations'] })
    },
  })
  
  const deleteMutation = useMutation({
    mutationFn: (id: string) => stationsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] })
    },
  })
  
  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      stationsApi.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] })
    },
  })
  
  const generateMutation = useMutation({
    mutationFn: (id: string) => stationsApi.generateEpisode(id, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stations'] })
    },
  })
  
  const handlePlayEpisode = (episode: Episode, stationTopic: string) => {
    if (episode.audio_url) {
      setCurrentAudio({
        id: episode.id,
        type: 'episode',
        title: `${stationTopic}: ${episode.title}`,
        audioUrl: episode.audio_url,
        transcript: episode.transcript,
      })
      setIsPlaying(true)
    }
  }
  
  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (topic.trim()) {
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
          Live Stations
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Subscribe to topics and receive automatic audio updates
        </p>
      </div>
      
      {/* Create new station */}
      <form onSubmit={handleCreate} className="card mb-6 sm:mb-8">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Radio className="w-5 h-5 text-accent" />
          Create New Station
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="label">Topic</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g., AI News, Cryptocurrency, Climate Change"
              className="input"
            />
          </div>
          
          <div>
            <label className="label">Description (optional)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of what you want to track"
              className="input"
            />
          </div>
          
          <div>
            <label className="label">Update Frequency</label>
            <div className="flex items-center gap-2 sm:gap-4 overflow-x-auto pb-1">
              {[6, 12, 24].map((hours) => (
                <button
                  key={hours}
                  type="button"
                  onClick={() => setFrequency(hours)}
                  className={clsx(
                    'px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap min-h-[40px]',
                    frequency === hours
                      ? 'bg-accent text-white'
                      : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                  )}
                >
                  Every {hours}h
                </button>
              ))}
            </div>
          </div>
          
          {/* Cast selector */}
          {castsData && castsData.casts.length > 0 && (
            <div>
              <label className="label">Cast (optional - uses default if not selected)</label>
              <select
                value={selectedCastId || ''}
                onChange={(e) => setSelectedCastId(e.target.value || undefined)}
                className="input"
              >
                <option value="">
                  Default ({castsData.casts.find(c => c.is_default)?.name || 'Alex and Sam'})
                </option>
                {castsData.casts.map((cast) => (
                  <option key={cast.id} value={cast.id}>
                    {cast.name} {cast.is_default && '(Default)'}
                  </option>
                ))}
              </select>
            </div>
          )}
          
          <button
            type="submit"
            disabled={!topic.trim() || createMutation.isPending}
            className="btn btn-primary w-full sm:w-auto flex items-center justify-center gap-2"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-5 h-5" />
                Create Station
              </>
            )}
          </button>
        </div>
      </form>
      
      {/* Stations list */}
      <div className="space-y-3 sm:space-y-4">
        {isLoading ? (
          <div className="card flex items-center justify-center py-10 sm:py-12">
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="card text-center py-10 sm:py-12">
            <AlertCircle className="w-10 sm:w-12 h-10 sm:h-12 text-red-500 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">Failed to load stations. Is the backend running?</p>
          </div>
        ) : data?.stations.length === 0 ? (
          <div className="card text-center py-10 sm:py-12">
            <Radio className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">No stations yet. Create your first one!</p>
          </div>
        ) : (
          data?.stations.map((station) => (
            <div
              key={station.id}
              className="card hover:border-augustus-700 transition-colors"
            >
              {/* Station header */}
              <div className="flex items-center gap-3 sm:gap-4">
                {/* Status indicator */}
                <div
                  className={clsx(
                    'w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center flex-shrink-0',
                    station.is_active
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-augustus-800 text-augustus-500'
                  )}
                >
                  <Radio className="w-5 h-5 sm:w-6 sm:h-6" />
                </div>
                
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-white text-sm sm:text-base">{station.topic}</h3>
                  {station.description && (
                    <p className="text-xs sm:text-sm text-augustus-400 truncate">{station.description}</p>
                  )}
                  <div className="flex flex-wrap items-center gap-x-3 sm:gap-x-4 gap-y-1 text-xs sm:text-sm text-augustus-500 mt-1">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      Every {station.update_frequency_hours}h
                    </span>
                    <span>{station.episode_count} episodes</span>
                  </div>
                </div>
                
                {/* Actions */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => generateMutation.mutate(station.id)}
                    disabled={generateMutation.isPending}
                    className="btn btn-ghost p-2"
                    title="Generate new episode"
                  >
                    <RefreshCw className={clsx(
                      'w-4 h-4 sm:w-5 sm:h-5',
                      generateMutation.isPending && 'animate-spin'
                    )} />
                  </button>
                  
                  <button
                    onClick={() => toggleMutation.mutate({
                      id: station.id,
                      is_active: !station.is_active,
                    })}
                    className={clsx(
                      'btn btn-ghost p-2',
                      station.is_active ? 'text-green-400' : 'text-augustus-500'
                    )}
                    title={station.is_active ? 'Pause station' : 'Resume station'}
                  >
                    {station.is_active ? (
                      <Pause className="w-4 h-4 sm:w-5 sm:h-5" />
                    ) : (
                      <Play className="w-4 h-4 sm:w-5 sm:h-5" />
                    )}
                  </button>
                  
                  <button
                    onClick={() => setExpandedStation(
                      expandedStation === station.id ? null : station.id
                    )}
                    className="btn btn-ghost p-2"
                  >
                    {expandedStation === station.id ? (
                      <ChevronUp className="w-4 h-4 sm:w-5 sm:h-5" />
                    ) : (
                      <ChevronDown className="w-4 h-4 sm:w-5 sm:h-5" />
                    )}
                  </button>
                  
                  <button
                    onClick={() => deleteMutation.mutate(station.id)}
                    className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4 sm:w-5 sm:h-5" />
                  </button>
                </div>
              </div>
              
              {/* Episodes */}
              {expandedStation === station.id && station.episodes.length > 0 && (
                <div className="mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-augustus-800/50 space-y-2">
                  {station.episodes.map((episode) => (
                    <div
                      key={episode.id}
                      className="flex items-center gap-2 sm:gap-3 p-2 sm:p-3 bg-augustus-950/50 rounded-lg"
                    >
                      <button
                        onClick={() => handlePlayEpisode(episode, station.topic)}
                        disabled={episode.status !== 'completed'}
                        className={clsx(
                          'w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center flex-shrink-0',
                          episode.status === 'completed'
                            ? 'bg-accent hover:bg-accent-600 text-white active:scale-95'
                            : 'bg-augustus-800 text-augustus-500'
                        )}
                      >
                        {episode.status === 'generating' ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Play className="w-4 h-4 ml-0.5" />
                        )}
                      </button>
                      
                      <div className="flex-1 min-w-0">
                        <p className="text-xs sm:text-sm font-medium text-white truncate">
                          {episode.title}
                        </p>
                        <p className="text-xs text-augustus-500">
                          {formatDuration(episode.duration_seconds)} • {formatDate(episode.created_at)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
