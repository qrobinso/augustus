import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { X, Clock, Mail, Webhook } from 'lucide-react'
import { scheduledBriefingsApi, topicsApi, settingsApi, ScheduledBriefing } from '../api/client'

interface ScheduledBriefingFormProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  editingSchedule?: ScheduledBriefing | null
  initialTopicIds?: string[]
}

const DAYS_OF_WEEK = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
]

export default function ScheduledBriefingForm({
  isOpen,
  onClose,
  onSuccess,
  editingSchedule,
  initialTopicIds = [],
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
  const [timezone, setTimezone] = useState('UTC')
  
  // Fetch topics and settings
  const { data: topicsData } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })
  
  const topics = topicsData?.topics || []
  
  useEffect(() => {
    if (settings?.timezone) {
      setTimezone(settings.timezone)
    }
  }, [settings])
  
  useEffect(() => {
    if (editingSchedule) {
      setName(editingSchedule.name)
      setSelectedTopicIds(editingSchedule.topic_ids || [])
      setScheduleTime(editingSchedule.schedule_time)
      setScheduleDays(editingSchedule.schedule_days || [])
      setNotificationMethods(editingSchedule.notification_methods || [])
      setEmailRecipients(editingSchedule.email_recipients?.join(', ') || '')
      setWebhookUrl(editingSchedule.webhook_url || '')
      setMaxDurationMinutes(editingSchedule.max_duration_minutes || 5)
      setIsActive(editingSchedule.is_active)
    } else {
      // Reset form
      setName('')
      setSelectedTopicIds(initialTopicIds || [])
      setScheduleTime('08:00')
      setScheduleDays([0, 1, 2, 3, 4]) // Default to weekdays
      setNotificationMethods([])
      setEmailRecipients('')
      setWebhookUrl('')
      setMaxDurationMinutes(settings?.briefing_duration_minutes || 5)
      setIsActive(true)
    }
  }, [editingSchedule, settings, initialTopicIds])
  
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
    
    // Validation
    if (!name.trim()) {
      alert('Please enter a name for the schedule')
      return
    }
    
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
      name: name.trim(),
      topic_ids: selectedTopicIds.length > 0 ? selectedTopicIds : undefined,
      schedule_time: scheduleTime,
      schedule_days: scheduleDays,
      notification_methods: notificationMethods,
      email_recipients: notificationMethods.includes('email') ? emailRecipientsList : undefined,
      webhook_url: notificationMethods.includes('webhook') ? webhookUrl.trim() : undefined,
      is_active: isActive,
      max_duration_minutes: maxDurationMinutes,
    }
    
    if (editingSchedule) {
      updateMutation.mutate({ id: editingSchedule.id, ...payload })
    } else {
      createMutation.mutate(payload)
    }
  }
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-semibold text-white">
            {editingSchedule ? 'Edit Scheduled Briefing' : 'Create Scheduled Briefing'}
          </h2>
          <button
            onClick={onClose}
            className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Name */}
          <div>
            <label className="label">Schedule Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Morning Briefing, Weekly Summary"
              className="input"
              required
            />
          </div>
          
          {/* Topics */}
          <div>
            <label className="label">Topics (optional - leave empty for all topics)</label>
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
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5 ${
                      selectedTopicIds.includes(topic.id)
                        ? 'text-white'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                    }`}
                    style={
                      selectedTopicIds.includes(topic.id)
                        ? { backgroundColor: topic.color || '#3B82F6' }
                        : undefined
                    }
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
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                    scheduleDays.includes(day.value)
                      ? 'bg-accent text-white'
                      : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                  }`}
                >
                  {day.label}
                </button>
              ))}
            </div>
          </div>
          
          {/* Notification Methods */}
          <div>
            <label className="label">
              Notification Methods (optional - leave empty to generate briefing without notifications)
            </label>
            <p className="text-xs text-augustus-500 mb-2">
              If no notification methods are selected, the briefing will be generated and available on the dashboard.
            </p>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notificationMethods.includes('email')}
                  onChange={() => toggleNotificationMethod('email')}
                  className="w-4 h-4"
                />
                <Mail className="w-4 h-4 text-augustus-400" />
                <span className="text-augustus-300">Email</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notificationMethods.includes('webhook')}
                  onChange={() => toggleNotificationMethod('webhook')}
                  className="w-4 h-4"
                />
                <Webhook className="w-4 h-4 text-augustus-400" />
                <span className="text-augustus-300">Webhook</span>
              </label>
            </div>
          </div>
          
          {/* Email Recipients */}
          {notificationMethods.includes('email') && (
            <div>
              <label className="label">Email Recipients (comma-separated)</label>
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
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-augustus-300">Active (enabled)</span>
            </label>
          </div>
          
          {/* Actions */}
          <div className="flex gap-4 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-ghost flex-1"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary flex-1"
            >
              {editingSchedule ? 'Update' : 'Create'} Schedule
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
