import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Loader2, 
  Sparkles, 
  Clock, 
  Calendar,
  Trash2,
  Plus,
  Pencil,
  Mail,
  Webhook,
  Power
} from 'lucide-react'
import clsx from 'clsx'
import { scheduledBriefingsApi, castsApi } from '../api/client'

export default function DashboardSchedules() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  const [selectedTopicIds] = useState<string[]>([])
  const [selectedCastId, setSelectedCastId] = useState<string | undefined>(() => {
    const saved = localStorage.getItem('selectedCastId')
    return saved || undefined
  })
  
  // Fetch scheduled briefings
  const { data: scheduledData, isLoading: scheduledLoading } = useQuery({
    queryKey: ['scheduled-briefings'],
    queryFn: () => scheduledBriefingsApi.list(),
  })
  
  // Fetch casts
  const { data: castsData } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
  const scheduledBriefings = scheduledData?.scheduled_briefings || []
  const casts = castsData?.casts || []
  const defaultCast = casts.find(c => c.is_default)
  
  // Initialize selectedCastId with default cast
  useEffect(() => {
    if (defaultCast && selectedCastId === undefined) {
      setSelectedCastId(defaultCast.id)
    }
  }, [defaultCast, selectedCastId])
  
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
  
  const triggerScheduleMutation = useMutation({
    mutationFn: (id: string) => scheduledBriefingsApi.trigger(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
      queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
    },
  })

  return (
    <div className="card mb-6 sm:mb-8">
      <div className="flex items-center justify-between gap-2 mb-4">
        <h2 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
          <Calendar className="w-5 h-5 text-accent" />
          Scheduled Briefings
          {scheduledBriefings.length > 0 && (
            <span className="text-xs sm:text-sm font-normal text-augustus-500">
              ({scheduledBriefings.length})
            </span>
          )}
        </h2>
        <button
          onClick={() => {
            const params = new URLSearchParams()
            if (selectedTopicIds.length > 0) {
              params.set('topicIds', selectedTopicIds.join(','))
            }
            if (selectedCastId) {
              params.set('castId', selectedCastId)
            }
            navigate(`/schedules/create?${params.toString()}`)
          }}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">New Schedule</span>
        </button>
      </div>
      
      {scheduledLoading ? (
        <div className="flex items-center justify-center py-6 sm:py-8">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : scheduledBriefings.length === 0 ? (
        <div className="text-center py-6 sm:py-8">
          <Calendar className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
          <p className="text-sm sm:text-base text-augustus-400 mb-1">No scheduled briefings yet.</p>
          <p className="text-xs sm:text-sm text-augustus-500 mb-4">Set up automatic briefings to be generated at specific times.</p>
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
                className="p-3 sm:p-4 bg-augustus-900 rounded-lg border border-augustus-800 hover:border-augustus-700 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 sm:gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5 sm:mb-2 flex-wrap">
                      <h3 className="font-semibold text-white text-sm sm:text-base">{schedule.name}</h3>
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
                    <div className="flex flex-wrap items-center gap-x-3 sm:gap-x-4 gap-y-1 text-xs sm:text-sm text-augustus-400">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                        {schedule.schedule_time}
                      </span>
                      <span>{daysLabels}</span>
                      <span className="flex items-center gap-1">
                        {schedule.notification_methods.length > 0 ? (
                          <>
                            {schedule.notification_methods.includes('email') && (
                              <Mail className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                            )}
                            {schedule.notification_methods.includes('webhook') && (
                              <Webhook className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                            )}
                          </>
                        ) : (
                          <span className="text-augustus-500 text-xs">Dashboard only</span>
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => navigate(`/schedules/${schedule.id}/edit`)}
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
                
                {/* Manual Trigger Button */}
                <div className="mt-3 pt-3 border-t border-augustus-800/50">
                  <button
                    onClick={() => triggerScheduleMutation.mutate(schedule.id)}
                    disabled={triggerScheduleMutation.isPending || !schedule.is_active}
                    className={clsx(
                      'btn btn-primary flex items-center justify-center gap-2 w-full sm:w-auto',
                      !schedule.is_active && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    {triggerScheduleMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Generate Now
                      </>
                    )}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}





