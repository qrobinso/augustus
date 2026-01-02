import { useState, useEffect, useRef, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { X, Clock, Mail, Webhook, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { scheduledBriefingsApi, topicsApi, settingsApi, castsApi, ScheduledBriefing } from '../api/client'

interface ScheduledBriefingFormProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  editingSchedule?: ScheduledBriefing | null
  initialTopicIds?: string[]
  initialCastId?: string
}

const DAYS_OF_WEEK = [
  { value: 0, label: 'Mon', fullLabel: 'Monday' },
  { value: 1, label: 'Tue', fullLabel: 'Tuesday' },
  { value: 2, label: 'Wed', fullLabel: 'Wednesday' },
  { value: 3, label: 'Thu', fullLabel: 'Thursday' },
  { value: 4, label: 'Fri', fullLabel: 'Friday' },
  { value: 5, label: 'Sat', fullLabel: 'Saturday' },
  { value: 6, label: 'Sun', fullLabel: 'Sunday' },
]

export default function ScheduledBriefingForm({
  isOpen,
  onClose,
  onSuccess,
  editingSchedule,
  initialTopicIds = [],
  initialCastId,
}: ScheduledBriefingFormProps) {
  const [name, setName] = useState('')
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([])
  const [scheduleTime, setScheduleTime] = useState('08:00')
  const [scheduleDays, setScheduleDays] = useState<number[]>([])
  const [notificationMethods, setNotificationMethods] = useState<string[]>([])
  const [emailRecipients, setEmailRecipients] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [maxDurationMinutes, setMaxDurationMinutes] = useState(5)
  const [isActive, setIsActive] = useState(true)
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(undefined)
  
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
  
  const topics = topicsData?.topics || []
  
  // Get timezone from settings (defaults to UTC to match backend default)
  // Don't fallback to browser timezone as that could cause confusion with scheduler
  const timezone = settings?.timezone || 'UTC'
  
  // Stabilize initialTopicIds array to prevent reference changes
  // Convert to string for stable comparison
  const initialTopicIdsStr = useMemo(() => {
    if (!initialTopicIds || initialTopicIds.length === 0) return ''
    return initialTopicIds.join(',')
  }, [initialTopicIds ? initialTopicIds.join(',') : ''])
  
  const stableInitialTopicIds = useMemo(() => {
    return initialTopicIds || []
  }, [initialTopicIdsStr])
  
  // Track previous values to prevent unnecessary updates
  const prevEditingScheduleIdRef = useRef<string | null>(null)
  const prevInitialTopicIdsRef = useRef<string>('')
  const prevInitialCastIdRef = useRef<string | undefined>(undefined)
  const prevSettingsDurationRef = useRef<number | undefined>(undefined)
  const wasOpenRef = useRef(false)
  
  useEffect(() => {
    // Reset refs when modal closes
    if (!isOpen) {
      if (wasOpenRef.current) {
        prevEditingScheduleIdRef.current = null
        prevInitialTopicIdsRef.current = ''
        prevInitialCastIdRef.current = undefined
        prevSettingsDurationRef.current = undefined
      }
      wasOpenRef.current = false
      return
    }
    
    wasOpenRef.current = true
    
    const currentEditingScheduleId = editingSchedule?.id || null
    const currentInitialTopicIdsStr = initialTopicIdsStr
    const currentSettingsDuration = settings?.briefing_duration_minutes
    
    // Check if we actually need to update
    if (editingSchedule) {
      // Only update if editingSchedule changed
      if (currentEditingScheduleId !== prevEditingScheduleIdRef.current) {
        setName(editingSchedule.name)
        setSelectedTopicIds(editingSchedule.topic_ids || [])
        setScheduleTime(editingSchedule.schedule_time)
        setScheduleDays(editingSchedule.schedule_days || [])
        setNotificationMethods(editingSchedule.notification_methods || [])
        setEmailRecipients(editingSchedule.email_recipients?.join(', ') || '')
        setWebhookUrl(editingSchedule.webhook_url || '')
        setMaxDurationMinutes(editingSchedule.max_duration_minutes || 5)
        setIsActive(editingSchedule.is_active)
        setSelectedCastId(editingSchedule.cast_id)
        prevEditingScheduleIdRef.current = currentEditingScheduleId
      }
    } else {
      // Only update if initial values actually changed
      if (
        currentInitialTopicIdsStr !== prevInitialTopicIdsRef.current ||
        initialCastId !== prevInitialCastIdRef.current ||
        currentSettingsDuration !== prevSettingsDurationRef.current
      ) {
        setName('')
        setSelectedTopicIds(stableInitialTopicIds)
        setScheduleTime('08:00')
        setScheduleDays([0, 1, 2, 3, 4]) // Default to weekdays
        setNotificationMethods([])
        setEmailRecipients('')
        setWebhookUrl('')
        setMaxDurationMinutes(currentSettingsDuration || 5)
        setIsActive(true)
        setSelectedCastId(initialCastId)
        prevInitialTopicIdsRef.current = currentInitialTopicIdsStr
        prevInitialCastIdRef.current = initialCastId
        prevSettingsDurationRef.current = currentSettingsDuration
        prevEditingScheduleIdRef.current = null
      }
    }
  }, [isOpen, editingSchedule?.id, initialTopicIdsStr, stableInitialTopicIds, initialCastId, settings?.briefing_duration_minutes])
  
  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])
  
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
      onSuccess()
      onClose()
    },
    onError: (error: any) => {
      alert(`Failed to create schedule: ${error.message || 'Unknown error'}`)
    },
  })
  
  const updateMutation = useMutation({
    mutationFn: ({ id, ...payload }: { id: string; [key: string]: any }) =>
      scheduledBriefingsApi.update(id, payload),
    onSuccess: () => {
      onSuccess()
      onClose()
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
    
    if (editingSchedule) {
      updateMutation.mutate({ id: editingSchedule.id, ...payload })
    } else {
      createMutation.mutate(payload)
    }
  }
  
  if (!isOpen) return null
  
  const isPending = createMutation.isPending || updateMutation.isPending
  
  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal - Bottom sheet on mobile, centered on desktop */}
      <div className={clsx(
        "absolute bg-augustus-900 border border-augustus-800/50 overflow-hidden",
        // Mobile: bottom sheet
        "inset-x-0 bottom-0 rounded-t-2xl max-h-[90vh]",
        // Desktop: centered modal
        "sm:inset-auto sm:top-1/2 sm:left-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl sm:max-w-lg sm:w-full sm:max-h-[85vh]"
      )}>
        {/* Mobile handle */}
        <div className="sm:hidden w-10 h-1 bg-augustus-600 rounded-full mx-auto mt-3" />
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-augustus-800/50">
          <h2 className="text-lg sm:text-xl font-semibold text-white">
            {editingSchedule ? 'Edit Schedule' : 'Create Schedule'}
          </h2>
          <button
            onClick={onClose}
            className="btn btn-ghost p-2 text-augustus-400 hover:text-white -mr-2"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Form content - scrollable */}
        <form onSubmit={handleSubmit} className="overflow-y-auto max-h-[calc(90vh-140px)] sm:max-h-[calc(85vh-140px)]">
          <div className="p-4 sm:p-6 space-y-5 sm:space-y-6">
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
          
          {/* Actions - Sticky at bottom */}
          <div className="sticky bottom-0 p-4 sm:p-6 border-t border-augustus-800/50 bg-augustus-900 pb-safe">
            <div className="flex flex-col-reverse sm:flex-row gap-3 sm:gap-4">
              <button
                type="button"
                onClick={onClose}
                className="btn btn-ghost flex-1"
                disabled={isPending}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary flex-1 flex items-center justify-center gap-2"
                disabled={isPending}
              >
                {isPending ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    {editingSchedule ? 'Updating...' : 'Creating...'}
                  </>
                ) : (
                  <>{editingSchedule ? 'Update' : 'Create'} Schedule</>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
