import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play,
  Loader2, 
  Sparkles, 
  FileText,
  CheckCircle,
  XCircle,
  Plus,
  Tag
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, topicsApi, castsApi, Briefing } from '../api/client'
import { useStore } from '../store/useStore'

export default function DashboardGenerate() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const setCurrentAudio = useStore((s) => s.setCurrentAudio)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  const playAudio = useStore((s) => s.playAudio)
  
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([])
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(() => {
    const saved = localStorage.getItem('selectedCastId')
    return saved || undefined
  })
  
  // Track previously in-progress briefings to detect completion
  const prevInProgressIdsRef = useRef<Set<string>>(new Set())
  const autoPlayedBriefingsRef = useRef<Set<string>>(new Set())
  
  // Check if there's a briefing in progress
  const hasBriefingInProgress = (briefings: Briefing[] | undefined) => 
    briefings?.some((b) => b.status === 'pending' || b.status === 'generating')
  
  const { data } = useQuery({
    queryKey: ['briefings'],
    queryFn: () => briefingsApi.list(10, 0),
    refetchInterval: (query) => {
      return hasBriefingInProgress(query.state.data?.briefings) ? 2000 : 10000
    },
  })
  
  // Fetch topics
  const { data: topicsData, isLoading: topicsLoading } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  // Fetch casts
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  const topics = topicsData?.topics || []
  const casts = castsData?.casts || []
  const defaultCast = casts.find(c => c.is_default)
  
  // Check if there's a briefing currently in progress
  const briefingInProgress = data?.briefings.find(
    (b) => b.status === 'pending' || b.status === 'generating'
  )
  
  // Find newly completed briefing
  const newlyCompletedBriefing = useMemo(() => {
    if (!data?.briefings) return null
    
    const currentInProgressIds = new Set(
      data.briefings
        .filter((b) => b.status === 'pending' || b.status === 'generating')
        .map((b) => b.id)
    )
    
    const completedIds = prevInProgressIdsRef.current
    const newlyCompleted = data.briefings.find(
      (b) => b.status === 'completed' && 
             completedIds.has(b.id) && 
             !currentInProgressIds.has(b.id) &&
             b.audio_url
    )
    
    prevInProgressIdsRef.current = currentInProgressIds
    
    return newlyCompleted || null
  }, [data?.briefings])
  
  // Handle starting playback and navigating
  const handlePlayAndNavigate = (briefing: Briefing) => {
    if (!briefing.audio_url) return
    
    playAudio({
      id: briefing.id,
      type: 'briefing',
      title: briefing.title,
      audioUrl: briefing.audio_url,
      transcript: briefing.transcript,
      chapters: briefing.chapters,
      initialPosition: briefing.playback_position || undefined,
    })
    
    navigate(`/briefing/${briefing.id}`)
  }
  
  // Auto-play when a briefing finishes
  useEffect(() => {
    if (newlyCompletedBriefing && newlyCompletedBriefing.audio_url) {
      if (!autoPlayedBriefingsRef.current.has(newlyCompletedBriefing.id)) {
        autoPlayedBriefingsRef.current.add(newlyCompletedBriefing.id)
        
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
      prevInProgressIdsRef.current = new Set()
      autoPlayedBriefingsRef.current.clear()
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
    onError: (error: Error & { response?: { status: number } }) => {
      if (error.response?.status === 409) {
        queryClient.invalidateQueries({ queryKey: ['briefings'] })
      }
    },
  })
  
  const cancelMutation = useMutation({
    mutationFn: (id: string) => briefingsApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
    },
  })
  
  // Persist selectedCastId to localStorage
  useEffect(() => {
    if (selectedCastId) {
      localStorage.setItem('selectedCastId', selectedCastId)
    }
  }, [selectedCastId])
  
  // Initialize selectedCastId with default cast
  useEffect(() => {
    if (defaultCast && selectedCastId === undefined) {
      setSelectedCastId(defaultCast.id)
    }
  }, [defaultCast, selectedCastId])
  
  // Validate selectedCastId exists
  useEffect(() => {
    if (casts.length > 0 && selectedCastId) {
      const castExists = casts.some(c => c.id === selectedCastId)
      if (!castExists) {
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
  
  const handleGenerate = () => {
    generateMutation.mutate({
      topicIds: selectedTopicIds.length > 0 ? selectedTopicIds : undefined,
      castId: selectedCastId,
    })
  }
  
  // Animation items for progress
  const animationItems = useMemo(() => {
    if (!briefingInProgress) return []
    
    const items: Array<{ type: 'topic' | 'source' | 'article' | 'step'; text: string }> = []
    
    const selectedTopics = topics.filter(t => selectedTopicIds.includes(t.id))
    selectedTopics.forEach(topic => {
      items.push({ type: 'topic', text: topic.name })
    })
    
    if (briefingInProgress.sources && briefingInProgress.sources.length > 0) {
      briefingInProgress.sources.slice(0, 5).forEach(source => {
        items.push({ type: 'source', text: source.title })
      })
    }
    
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
    
    useEffect(() => {
      itemsRef.current = items
      if (items.length > 0 && currentIndex >= items.length) {
        setCurrentIndex(0)
      }
    }, [items, currentIndex])
    
    useEffect(() => {
      if (items.length === 0) {
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
      
      if (!isInitializedRef.current) {
        isInitializedRef.current = true
        setFadeState('in')
        
        intervalRef.current = setInterval(() => {
          setFadeState('out')
          
          timeoutRef.current = setTimeout(() => {
            setCurrentIndex((prev) => {
              const currentItems = itemsRef.current
              if (currentItems.length === 0) return 0
              return (prev + 1) % currentItems.length
            })
            setFadeState('in')
          }, 500)
        }, 2500)
      }
    }, [])
    
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

  return (
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
      {newlyCompletedBriefing && !briefingInProgress && (
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
                
                {animationItems.length > 0 && (
                  <div className="mb-2 sm:mb-3">
                    <AnimatedGenerationItem items={animationItems} />
                  </div>
                )}
                
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
  )
}

