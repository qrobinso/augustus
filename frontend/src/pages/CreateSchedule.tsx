import { useState, useEffect, useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useProfileNavigate } from '../utils/profileSlug'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Clock, Mail, Webhook, Loader2, Calendar } from 'lucide-react'
import clsx from 'clsx'
import { scheduledBriefingsApi, topicsApi, settingsApi, castsApi } from '../api/client'

const DAYS_OF_WEEK = [
  { value: 0, label: 'Mon', fullLabel: 'Monday' },
  { value: 1, label: 'Tue', fullLabel: 'Tuesday' },
  { value: 2, label: 'Wed', fullLabel: 'Wednesday' },
  { value: 3, label: 'Thu', fullLabel: 'Thursday' },
  { value: 4, label: 'Fri', fullLabel: 'Friday' },
  { value: 5, label: 'Sat', fullLabel: 'Saturday' },
  { value: 6, label: 'Sun', fullLabel: 'Sunday' },
]

export default function CreateSchedule() {
  const navigate = useProfileNavigate()
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  
  const isEditing = Boolean(id)
  
  // Get initial values from URL params (for creating from Dashboard)
  const initialTopicIds = useMemo(() => {
    const topicIds = searchParams.get('topicIds')
    return topicIds ? topicIds.split(',') : []
  }, [searchParams])
  
  const initialCastId = searchParams.get('castId') || undefined
  
  const [name, setName] = useState('')
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([])
  const [scheduleTime, setScheduleTime] = useState('08:00')
  const [scheduleDays, setScheduleDays] = useState<number[]>([0, 1, 2, 3, 4]) // Default to weekdays
  const [notificationMethods, setNotificationMethods] = useState<string[]>([])
  const [emailRecipients, setEmailRecipients] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [maxDurationMinutes, setMaxDurationMinutes] = useState(5)
  const [isActive, setIsActive] = useState(true)
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(undefined)
  const [isInitialized, setIsInitialized] = useState(false)
  
  // Fetch topics and settings
  const { data: topicsData } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })
  
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  // Fetch existing schedule if editing
  const { data: existingSchedule, isLoading: scheduleLoading } = useQuery({
    queryKey: ['scheduled-briefing', id],
    queryFn: () => scheduledBriefingsApi.get(id!),
    enabled: isEditing,
  })
  
  const topics = topicsData?.topics || []
  
  // Get timezone from settings (defaults to UTC to match backend default)
  const timezone = settings?.timezone || 'UTC'
  
  // Initialize form with existing schedule data or defaults
  useEffect(() => {
    if (isInitialized) return
    
    if (isEditing && existingSchedule) {
      setName(existingSchedule.name)
      setSelectedTopicIds(existingSchedule.topic_ids || [])
      setScheduleTime(existingSchedule.schedule_time)
      setScheduleDays(existingSchedule.schedule_days || [])
      setNotificationMethods(existingSchedule.notification_methods || [])
      setEmailRecipients(existingSchedule.email_recipients?.join(', ') || '')
      setWebhookUrl(existingSchedule.webhook_url || '')
      setMaxDurationMinutes(existingSchedule.max_duration_minutes || 5)
      setIsActive(existingSchedule.is_active)
      setSelectedCastId(existingSchedule.cast_id)
      setIsInitialized(true)
    } else if (!isEditing && settings) {
      // Initialize with URL params and settings for new schedule
      setSelectedTopicIds(initialTopicIds)
      setSelectedCastId(initialCastId)
      setMaxDurationMinutes(settings.briefing_duration_minutes || 5)
      setIsInitialized(true)
    }
  }, [isEditing, existingSchedule, settings, initialTopicIds, initialCastId, isInitialized])
  
  const toggleDay = (day: number) => {
    setScheduleDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    )
  }
  
  const toggleNotificationMethod = (method: string) => {
    setNotificationMethods((prev) =>
      prev.includes(method)
        ? prev.filter((m) => m !== method)
        : [...prev, method]
    )
  }
  
  const toggleTopic = (topicId: string) => {
    setSelectedTopicIds((prev) =>
      prev.includes(topicId)
        ? prev.filter((id) => id !== topicId)
        : [...prev, topicId]
    )
  }
  
  // Generate a name based on selected topics
  const generateScheduleName = () => {
    if (selectedTopicIds.length === 0) {
      return 'All Topics Briefing'
    }
    
    const selectedTopicNames = topics
      .filter((t) => selectedTopicIds.includes(t.id))
      .map((t) => t.name)
    
    if (selectedTopicNames.length === 1) {
      return `${selectedTopicNames[0]} Briefing`
    } else if (selectedTopicNames.length === 2) {
      return `${selectedTopicNames[0]} & ${selectedTopicNames[1]} Briefing`
    } else {
      return `${selectedTopicNames[0]}, ${selectedTopicNames[1]} +${selectedTopicNames.length - 2} more`
    }
  }
  
  const createMutation = useMutation({
    mutationFn: (payload: any) => scheduledBriefingsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
      navigate('/dashboard/schedules')
    },
    onError: (error: any) => {
      alert(`Failed to create schedule: ${error.message || 'Unknown error'}`)
    },
  })
  
  const updateMutation = useMutation({
    mutationFn: ({ id, ...payload }: { id: string; [key: string]: any }) =>
      scheduledBriefingsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
      navigate('/dashboard/schedules')
    },
    onError: (error: any) => {
      alert(`Failed to update schedule: ${error.message || 'Unknown error'}`)
    },
  })
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Auto-generate name if not provided
    const scheduleName = name.trim() || generateScheduleName()
    
    if (scheduleDays.length === 0) {
      alert('Please select at least one day of the week')
      return
    }
    
    // Notification methods are optional - if none selected, briefing will just be generated without notifications
    if (notificationMethods.includes('email') && !emailRecipients.trim()) {
      alert('Please enter email recipients when email notification is enabled')
      return
    }
    
    if (notificationMethods.includes('webhook') && !webhookUrl.trim()) {
      alert('Please enter a webhook URL when webhook notification is enabled')
      return
    }
    
    // Parse email recipients
    const emailRecipientsList = emailRecipients
      .split(',')
      .map((email) => email.trim())
      .filter((email) => email.length > 0)
    
    if (notificationMethods.includes('email') && emailRecipientsList.length === 0) {
      alert('Please enter at least one valid email address')
      return
    }
    
    const payload = {
      name: scheduleName,
      topic_ids: selectedTopicIds.length > 0 ? selectedTopicIds : undefined,
      schedule_time: scheduleTime,
      schedule_days: scheduleDays,
      notification_methods: notificationMethods,
      email_recipients: notificationMethods.includes('email') ? emailRecipientsList : undefined,
      webhook_url: notificationMethods.includes('webhook') ? webhookUrl.trim() : undefined,
      is_active: isActive,
      max_duration_minutes: maxDurationMinutes,
      cast_id: selectedCastId,
    }
    
    if (isEditing && id) {
      updateMutation.mutate({ id, ...payload })
    } else {
      createMutation.mutate(payload)
    }
  }
  
  const isPending = createMutation.isPending || updateMutation.isPending
  
  // Show loading state while fetching existing schedule
  if (isEditing && scheduleLoading) {
    return (
      <div className="page-container flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-augustus-400 hover:text-white transition-colors mb-4"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back</span>
        </button>
        
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center">
            <Calendar className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white">
              {isEditing ? 'Edit Schedule' : 'Create Schedule'}
            </h1>
            <p className="text-sm sm:text-base text-augustus-400">
              {isEditing ? 'Update your scheduled briefing' : 'Set up automatic briefing generation'}
            </p>
          </div>
        </div>
      </div>
      
      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card space-y-5 sm:space-y-6">
          {/* Name */}
          <div>
            <label className="label">Schedule Name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Leave blank to auto-generate"
              className="input"
            />
            <p className="text-xs text-augustus-500 mt-1">
              {name.trim() ? '' : `Will be named: "${generateScheduleName()}"`}
            </p>
          </div>
          
          {/* Topics */}
          <div>
            <label className="label">Topics (optional)</label>
            {topics.length === 0 ? (
              <p className="text-sm text-augustus-500">
                No topics available. <a href="/topics" className="text-accent hover:underline">Create topics first</a>.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {topics.map((topic) => (
                  <button
                    key={topic.id}
                    type="button"
                    onClick={() => toggleTopic(topic.id)}
                    className={clsx(
                      'px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 min-h-[36px]',
                      selectedTopicIds.includes(topic.id)
                        ? 'text-white'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                    )}
                    style={
                      selectedTopicIds.includes(topic.id)
                        ? { backgroundColor: topic.color || '#3B82F6' }
                        : undefined
                    }
                  >
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
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
          
          {/* Schedule Time */}
          <div>
            <label className="label flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Schedule Time ({timezone})
            </label>
            <input
              type="time"
              value={scheduleTime}
              onChange={(e) => setScheduleTime(e.target.value)}
              className="input"
              required
            />
            <p className="text-xs text-augustus-500 mt-1">
              Time is in your configured timezone ({timezone}), not UTC
            </p>
          </div>
          
          {/* Days of Week */}
          <div>
            <label className="label">Days of Week</label>
            <div className="flex flex-wrap gap-2">
              {DAYS_OF_WEEK.map((day) => (
                <button
                  key={day.value}
                  type="button"
                  onClick={() => toggleDay(day.value)}
                  className={clsx(
                    'px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all min-h-[40px]',
                    scheduleDays.includes(day.value)
                      ? 'bg-accent text-white'
                      : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
                  )}
                >
                  <span className="sm:hidden">{day.label}</span>
                  <span className="hidden sm:inline">{day.fullLabel}</span>
                </button>
              ))}
            </div>
          </div>
          
          {/* Notification Methods */}
          <div>
            <label className="label">Notifications (optional)</label>
            <p className="text-xs text-augustus-500 mb-3">
              If none selected, briefings appear on dashboard only.
            </p>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer touch-target">
                <input
                  type="checkbox"
                  checked={notificationMethods.includes('email')}
                  onChange={() => toggleNotificationMethod('email')}
                  className="w-5 h-5 rounded border-augustus-600 bg-augustus-800 text-accent focus:ring-accent"
                />
                <Mail className="w-5 h-5 text-augustus-400" />
                <span className="text-sm sm:text-base text-augustus-300">Email</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer touch-target">
                <input
                  type="checkbox"
                  checked={notificationMethods.includes('webhook')}
                  onChange={() => toggleNotificationMethod('webhook')}
                  className="w-5 h-5 rounded border-augustus-600 bg-augustus-800 text-accent focus:ring-accent"
                />
                <Webhook className="w-5 h-5 text-augustus-400" />
                <span className="text-sm sm:text-base text-augustus-300">Webhook</span>
              </label>
            </div>
          </div>
          
          {/* Email Recipients */}
          {notificationMethods.includes('email') && (
            <div>
              <label className="label">Email Recipients</label>
              <input
                type="text"
                value={emailRecipients}
                onChange={(e) => setEmailRecipients(e.target.value)}
                placeholder="user@example.com, another@example.com"
                className="input"
              />
            </div>
          )}
          
          {/* Webhook URL */}
          {notificationMethods.includes('webhook') && (
            <div>
              <label className="label">Webhook URL</label>
              <input
                type="url"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://example.com/webhook"
                className="input"
              />
            </div>
          )}
          
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
          
          {/* Duration */}
          <div>
            <label className="label">Duration (minutes)</label>
            <input
              type="number"
              value={maxDurationMinutes}
              onChange={(e) => setMaxDurationMinutes(parseInt(e.target.value) || 5)}
              min={1}
              max={60}
              className="input"
            />
          </div>
          
          {/* Active Toggle */}
          <div>
            <label className="flex items-center gap-3 cursor-pointer touch-target">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="w-5 h-5 rounded border-augustus-600 bg-augustus-800 text-accent focus:ring-accent"
              />
              <span className="text-sm sm:text-base text-augustus-300">Active (enabled)</span>
            </label>
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex flex-col-reverse sm:flex-row gap-3 sm:gap-4">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="btn btn-ghost flex-1 sm:flex-none"
            disabled={isPending}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary flex-1 sm:flex-none flex items-center justify-center gap-2"
            disabled={isPending}
          >
            {isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {isEditing ? 'Updating...' : 'Creating...'}
              </>
            ) : (
              <>{isEditing ? 'Update' : 'Create'} Schedule</>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}




