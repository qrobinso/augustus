import { useState, useEffect } from 'react'
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
  CheckCircle,
  Circle,
  XCircle,
  Plus,
  Pencil,
  Mail,
  Webhook,
  Power,
  Tag
} from 'lucide-react'
import clsx from 'clsx'
import { briefingsApi, settingsApi, topicsApi, scheduledBriefingsApi, Briefing, ScheduledBriefing } from '../api/client'
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
  
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([])
  const [showScheduleForm, setShowScheduleForm] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<ScheduledBriefing | null>(null)
  const [listenedFilter, setListenedFilter] = useState<boolean | undefined>(undefined)
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 10
  
  // Check if there's a briefing in progress to determine poll interval
  const hasBriefingInProgress = (briefings: Briefing[] | undefined) => 
    briefings?.some((b) => b.status === 'pending' || b.status === 'generating')
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['briefings', listenedFilter, currentPage],
    queryFn: () => briefingsApi.list(pageSize, currentPage * pageSize, listenedFilter),
    refetchInterval: (query) => {
      // Poll more frequently (2s) when a briefing is in progress, otherwise every 10s
      return hasBriefingInProgress(query.state.data?.briefings) ? 2000 : 10000
    },
  })
  
  // Reset to first page when filter changes
  useEffect(() => {
    setCurrentPage(0)
  }, [listenedFilter])
  
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
  
  const topics = topicsData?.topics || []
  const scheduledBriefings = scheduledData?.scheduled_briefings || []
  // Use customer's timezone from settings for all displays
  const timezone = settings?.timezone || 'UTC'
  
  // Check if there's a briefing currently in progress
  const briefingInProgress = data?.briefings.find(
    (b) => b.status === 'pending' || b.status === 'generating'
  )
  
  const generateMutation = useMutation({
    mutationFn: (topicIds?: string[]) => briefingsApi.generate({ 
      topic_ids: topicIds && topicIds.length > 0 ? topicIds : undefined 
    }),
    onSuccess: () => {
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
  
  const handlePlayPause = (briefing: Briefing, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent navigation when clicking play
    
    if (!briefing.audio_url) return
    
    if (currentAudio?.id === briefing.id) {
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
  
  const truncateTranscript = (transcript?: string, maxLength = 150) => {
    if (!transcript) return null
    // Remove HOST1:/HOST2: prefixes for preview
    const cleaned = transcript.replace(/HOST[12]:\s*/gi, '').trim()
    if (cleaned.length <= maxLength) return cleaned
    return cleaned.substring(0, maxLength).trim() + '...'
  }
  
  const handleGenerate = () => {
    generateMutation.mutate(selectedTopicIds.length > 0 ? selectedTopicIds : undefined)
  }
  
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
  
  const formatDate = (dateStr: string) => {
    return formatCompactDate(dateStr, timezone)
  }
  
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-semibold text-white mb-2">
          Daily Briefings
        </h1>
        <p className="text-augustus-400">
          AI-generated audio briefings from your news feeds
        </p>
      </div>
      
      {/* Generate new briefing */}
      <div className="card mb-8">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-accent" />
          Generate New Briefing
        </h2>
        
        <div className="mb-4">
          <p className="text-sm text-augustus-400 mb-2">Select topics to include:</p>
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
                    'px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5',
                    selectedTopicIds.includes(topic.id)
                      ? 'text-white'
                      : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                  )}
                  style={selectedTopicIds.includes(topic.id) ? {
                    backgroundColor: topic.color || '#3B82F6',
                  } : undefined}
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: topic.color || '#3B82F6' }}
                  />
                  {topic.name}
                </button>
              ))}
            </div>
          )}
          {selectedTopicIds.length === 0 && topics.length > 0 && (
            <p className="text-xs text-augustus-500 mt-2">
              No topics selected - all topics will be included
            </p>
          )}
        </div>
        
        {/* Show in-progress message or generate button */}
        {briefingInProgress ? (
          <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3 flex-1">
                <Loader2 className="w-5 h-5 animate-spin text-yellow-400 mt-0.5" />
                <div className="flex-1">
                  <p className="text-yellow-400 font-medium">Generating briefing...</p>
                  <p className="text-sm text-augustus-400 mb-3">
                    {briefingInProgress.title}
                  </p>
                  
                  {/* Progress bar */}
                  {briefingInProgress.extra_data?.progress && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs">
                        <span className="text-augustus-400">
                          Step {briefingInProgress.extra_data.progress.step} of {briefingInProgress.extra_data.progress.total_steps}: {briefingInProgress.extra_data.progress.step_name}
                        </span>
                        <span className="text-augustus-500">
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
                className="btn btn-ghost p-2 text-augustus-400 hover:text-red-400 hover:bg-red-500/10"
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
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerate}
              disabled={generateMutation.isPending}
              className="btn btn-primary flex items-center gap-2"
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
            <button
              onClick={() => {
                setEditingSchedule(null)
                setShowScheduleForm(true)
              }}
              className="btn btn-primary flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add to Schedule
            </button>
          </div>
        )}
      </div>
      
      {/* Scheduled Briefings Section */}
      <div className="card mb-8">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Calendar className="w-5 h-5 text-accent" />
            Scheduled Briefings
          </h2>
        </div>
        
        {scheduledLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
          </div>
        ) : scheduledBriefings.length === 0 ? (
          <div className="text-center py-8">
            <Calendar className="w-12 h-12 text-augustus-600 mx-auto mb-4" />
            <p className="text-augustus-400 mb-4">No scheduled briefings yet.</p>
            <button
              onClick={() => {
                setEditingSchedule(null)
                setShowScheduleForm(true)
              }}
              className="btn btn-primary"
            >
              Add to Schedule
            </button>
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
                  className="p-4 bg-augustus-900 rounded-lg border border-augustus-800 hover:border-augustus-700 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold text-white">{schedule.name}</h3>
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
                      <div className="flex flex-wrap items-center gap-4 text-sm text-augustus-400">
                        <span className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          {schedule.schedule_time} ({timezone})
                        </span>
                        <span>{daysLabels}</span>
                        <span className="flex items-center gap-1">
                          {schedule.notification_methods.length > 0 ? (
                            <>
                              {schedule.notification_methods.includes('email') && (
                                <Mail className="w-4 h-4" />
                              )}
                              {schedule.notification_methods.includes('webhook') && (
                                <Webhook className="w-4 h-4" />
                              )}
                              {schedule.notification_methods.join(', ')}
                            </>
                          ) : (
                            <span className="text-augustus-500">No notifications (dashboard only)</span>
                          )}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-4 h-4" />
                          <span className="text-augustus-400">
                            Last generated:{' '}
                            {schedule.last_generated_at ? (
                              <span className="text-augustus-300">
                                {formatCompactDate(schedule.last_generated_at, timezone)}
                              </span>
                            ) : (
                              <span className="text-augustus-500 italic">Never</span>
                            )}
                          </span>
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
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
                </div>
              )
            })}
          </div>
        )}
      </div>
      
      {/* Briefings list */}
      <div className="space-y-4">
        {/* Filter and pagination controls */}
        <div className="card mb-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-augustus-400">Filter:</span>
              <button
                onClick={() => setListenedFilter(undefined)}
                className={clsx(
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                  listenedFilter === undefined
                    ? 'bg-accent text-white'
                    : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                )}
              >
                All
              </button>
              <button
                onClick={() => setListenedFilter(true)}
                className={clsx(
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5',
                  listenedFilter === true
                    ? 'bg-accent text-white'
                    : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                )}
              >
                <CheckCircle className="w-3 h-3" />
                Listened
              </button>
              <button
                onClick={() => setListenedFilter(false)}
                className={clsx(
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5',
                  listenedFilter === false
                    ? 'bg-accent text-white'
                    : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                )}
              >
                <Circle className="w-3 h-3" />
                Unlistened
              </button>
            </div>
            
            {/* Pagination */}
            {data && data.total > pageSize && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                  disabled={currentPage === 0}
                  className="btn btn-ghost px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-augustus-400">
                  Page {currentPage + 1} of {Math.ceil(data.total / pageSize)}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => p + 1)}
                  disabled={(currentPage + 1) * pageSize >= data.total}
                  className="btn btn-ghost px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
        
        {isLoading ? (
          <div className="card flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="card text-center py-12">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <p className="text-augustus-400">Failed to load briefings. Is the backend running?</p>
          </div>
        ) : data?.briefings.length === 0 ? (
          <div className="card text-center py-12">
            <Calendar className="w-12 h-12 text-augustus-600 mx-auto mb-4" />
            <p className="text-augustus-400">
              {listenedFilter === true
                ? 'No listened briefings found.'
                : listenedFilter === false
                ? 'No unlistened briefings found.'
                : 'No briefings yet. Generate your first one!'}
            </p>
          </div>
        ) : (
          data?.briefings.map((briefing) => {
            const isCurrentlyPlaying = currentAudio?.id === briefing.id && isPlaying
            // Get topic IDs from extra_data
            const briefingTopicIds = (briefing.extra_data?.topic_ids as string[]) || []
            // Match with topics data
            const briefingTopics = topics.filter((t) => briefingTopicIds.includes(t.id))
            
            return (
              <div
                key={briefing.id}
                onClick={() => navigate(`/briefing/${briefing.id}`)}
                className="card hover:border-augustus-600 transition-colors cursor-pointer group"
              >
                <div className="flex items-center gap-4">
                  {/* Play button */}
                  <button
                    onClick={(e) => handlePlayPause(briefing, e)}
                    disabled={briefing.status !== 'completed'}
                    className={clsx(
                      'w-14 h-14 rounded-full flex items-center justify-center flex-shrink-0 transition-all',
                      briefing.status === 'completed'
                        ? 'bg-accent hover:bg-accent-600 text-white glow'
                        : 'bg-augustus-800 text-augustus-500'
                    )}
                  >
                    {briefing.status === 'generating' || briefing.status === 'pending' ? (
                      <Loader2 className="w-6 h-6 animate-spin" />
                    ) : briefing.status === 'failed' || briefing.status === 'cancelled' ? (
                      <AlertCircle className="w-6 h-6 text-red-500" />
                    ) : isCurrentlyPlaying ? (
                      <Pause className="w-6 h-6" />
                    ) : (
                      <Play className="w-6 h-6 ml-1" />
                    )}
                  </button>
                  
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-white truncate group-hover:text-accent transition-colors">
                      {briefing.title}
                    </h3>
                    <div className="flex flex-wrap items-center gap-2 text-sm text-augustus-500 mb-2">
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
                        briefing.status === 'cancelled' && 'bg-augustus-700 text-augustus-500',
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
                    {/* Topics */}
                    {briefingTopics.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {briefingTopics.map((topic) => (
                          <span
                            key={topic.id}
                            className="px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1"
                            style={{ backgroundColor: `${topic.color || '#3B82F6'}20`, color: topic.color || '#3B82F6' }}
                          >
                            <span
                              className="w-1.5 h-1.5 rounded-full"
                              style={{ backgroundColor: topic.color || '#3B82F6' }}
                            />
                            {topic.name}
                          </span>
                        ))}
                      </div>
                    )}
                    {briefing.error_message && (
                      <p className="text-sm text-red-400 mt-1">{briefing.error_message}</p>
                    )}
                  </div>
                  
                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteMutation.mutate(briefing.id)
                      }}
                      className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                      title="Delete"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                    <ChevronRight className="w-5 h-5 text-augustus-600 group-hover:text-augustus-400 transition-colors" />
                  </div>
                </div>
                
                {/* Transcript preview */}
                {briefing.transcript && (
                  <div className="mt-3 pt-3 border-t border-augustus-800/50">
                    <div className="flex items-start gap-2">
                      <FileText className="w-4 h-4 text-augustus-500 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-augustus-400 line-clamp-2">
                        {truncateTranscript(briefing.transcript)}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
        
        {/* Pagination footer */}
        {data && data.total > pageSize && (
          <div className="card mt-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-augustus-400">
                Showing {currentPage * pageSize + 1} to {Math.min((currentPage + 1) * pageSize, data.total)} of {data.total} briefings
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                  disabled={currentPage === 0}
                  className="btn btn-ghost px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-augustus-400 px-2">
                  Page {currentPage + 1} of {Math.ceil(data.total / pageSize)}
                </span>
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
        editingSchedule={editingSchedule}
        initialTopicIds={selectedTopicIds}
      />
    </div>
  )
}
