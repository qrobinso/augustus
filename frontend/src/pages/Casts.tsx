import { useState } from 'react'
import { useProfileNavigate } from '../utils/profileSlug'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Users,
  Loader2, 
  Plus,
  Trash2,
  Pencil,
  Star,
  RotateCcw,
  ChevronDown
} from 'lucide-react'
import clsx from 'clsx'
import { castsApi, Cast } from '../api/client'
import { providerLabel, splitCastsByProvider, voiceName } from './castProviders'

export default function Casts() {
  const navigate = useProfileNavigate()
  const queryClient = useQueryClient()
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['casts', 'all'],
    queryFn: () => castsApi.list(undefined, 'all'),
  })
  const { data: voices } = useQuery({ queryKey: ['cast-voices'], queryFn: () => castsApi.voices(), staleTime: 30_000 })
  const [showOther, setShowOther] = useState(false)
  
  const deleteMutation = useMutation({
    mutationFn: (id: string) => castsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['casts'] })
    },
  })
  
  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => castsApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['casts'] })
    },
  })
  
  const restoreDefaultMutation = useMutation({
    mutationFn: () => castsApi.restoreDefault(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['casts'] })
    },
  })
  
  const activeProvider = data?.active_provider ?? ''
  const label = providerLabel(data?.providers ?? [], activeProvider)
  const { active: casts, other: otherCasts } = splitCastsByProvider(data?.casts ?? [], activeProvider)
  
  const handleDelete = async (cast: Cast) => {
    if (cast.is_default) {
      alert('Cannot delete the default cast')
      return
    }
    if (confirm(`Delete cast "${cast.name}"?`)) {
      deleteMutation.mutate(cast.id)
    }
  }
  
  const handleSetDefault = (cast: Cast) => {
    setDefaultMutation.mutate(cast.id)
  }
  
  const handleRestoreDefault = () => {
    if (confirm('Restore the default cast to Alex and Sebastian with the built-in Gemini voices?')) {
      restoreDefaultMutation.mutate()
    }
  }
  
  const handleEdit = (cast: Cast) => {
    navigate(`/casts/${cast.id}/edit`, { state: { from: '/casts' } })
  }
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-augustus-400" />
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
          Error loading casts: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    )
  }
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
            {label ? `${label} casts` : 'Casts'}
          </h1>
          <p className="text-sm sm:text-base text-augustus-400">
            Hosts for your active voice provider ·{' '}
            <button type="button" className="text-accent hover:underline" onClick={() => navigate('/settings')}>
              Change in Settings
            </button>
          </p>
        </div>
        <button
          onClick={() => navigate('/casts/create', { state: { from: '/casts' } })}
          className="btn btn-primary flex items-center gap-2 w-full sm:w-auto"
        >
          <Plus className="w-5 h-5" />
          Create Cast
        </button>
      </div>
      
      {casts.length === 0 ? (
        <div className="card text-center py-10 sm:py-12">
          <Users className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
          <p className="text-sm sm:text-base text-augustus-400 mb-4">No {label} casts yet. Briefings need one before they can play.</p>
          <button
            onClick={() => navigate('/casts/create', { state: { from: '/casts' } })}
            className="btn btn-primary"
          >
            Create a {label} cast
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {casts.map((cast) => (
            <div
              key={cast.id}
              className={clsx(
                'bg-augustus-800/50 rounded-lg p-6 border',
                cast.is_default && 'border-accent/50 bg-accent/5'
              )}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-semibold text-white">{cast.name}</h3>
                    {cast.is_default && (
                      <Star className="w-4 h-4 text-accent fill-accent" />
                    )}
                  </div>
                  {cast.is_default && (
                    <p className="text-xs text-augustus-500">Default cast</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleEdit(cast)}
                    className="btn-icon btn btn-ghost"
                    title="Edit"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  {!cast.is_default && (
                    <button
                      onClick={() => handleDelete(cast)}
                      className="btn-icon btn btn-ghost text-red-400 hover:text-red-300"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
              
              <div className="space-y-2">
                {cast.members.map((member) => (
                  <div
                    key={member.id}
                    className="bg-augustus-900/50 rounded p-3 text-sm"
                  >
                    <div className="font-medium text-white mb-1">{member.name}</div>
                    <div className="text-augustus-400 text-xs space-y-1">
                      <div>Voice: <span className="text-augustus-300">{voiceName(member.voice_id, voices?.voices ?? [])}</span></div>
                      <div>Personality: <span className="text-augustus-300">{member.personality}</span></div>
                    </div>
                  </div>
                ))}
              </div>
              
              {cast.is_default ? (
                activeProvider === 'gemini' && <button
                  onClick={handleRestoreDefault}
                  disabled={restoreDefaultMutation.isPending}
                  className="mt-4 w-full btn btn-sm btn-ghost text-xs flex items-center justify-center gap-2"
                >
                  {restoreDefaultMutation.isPending ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <RotateCcw className="w-3 h-3" />
                  )}
                  Restore Defaults
                </button>
              ) : (
                <button
                  onClick={() => handleSetDefault(cast)}
                  className="mt-4 w-full btn btn-sm btn-ghost text-xs"
                >
                  Set as Default
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {otherCasts.length > 0 && (
        <div className="mt-8">
          <button
            type="button"
            onClick={() => setShowOther(v => !v)}
            className="flex items-center gap-2 text-sm text-augustus-400 hover:text-augustus-300"
            aria-expanded={showOther}
          >
            <ChevronDown className={clsx('w-4 h-4 transition-transform', showOther && 'rotate-180')} />
            {otherCasts.length} cast{otherCasts.length === 1 ? '' : 's'} for other providers
          </button>
          {showOther && (
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 opacity-60">
              {otherCasts.map(cast => (
                <div key={cast.id} className="rounded-lg border border-augustus-700 bg-augustus-800/30 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-white">{cast.name}</h3>
                      <span className="mt-1 inline-block rounded bg-augustus-700 px-1.5 py-0.5 text-xs text-augustus-300">
                        {providerLabel(data?.providers ?? [], cast.tts_provider)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleEdit(cast)} className="btn-icon btn btn-ghost" title="View">
                        <Pencil className="w-4 h-4" />
                      </button>
                      {!cast.is_default && (
                        <button onClick={() => handleDelete(cast)} className="btn-icon btn btn-ghost text-red-400" title="Delete">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-augustus-500">
                    {cast.members.map(m => m.name).join(', ')} · switch provider in Settings to use
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}










