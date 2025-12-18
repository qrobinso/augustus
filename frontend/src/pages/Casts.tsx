import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Users,
  Loader2, 
  Plus,
  Trash2,
  Pencil,
  Star,
  X
} from 'lucide-react'
import clsx from 'clsx'
import { castsApi, Cast } from '../api/client'
import CastForm from '../components/CastForm'

const PERSONALITY_OPTIONS = [
  'Casual',
  'Professional',
  'Analytical',
  'Friendly',
  'Informative',
  'Upbeat',
]

export default function Casts() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingCast, setEditingCast] = useState<Cast | null>(null)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['casts'],
    queryFn: () => castsApi.list(),
  })
  
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
  
  const casts = data?.casts || []
  
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
  
  const handleEdit = (cast: Cast) => {
    if (cast.is_default) {
      alert('Cannot edit the default cast')
      return
    }
    setEditingCast(cast)
    setShowForm(true)
  }
  
  const handleFormClose = () => {
    setShowForm(false)
    setEditingCast(null)
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
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">Casts</h1>
          <p className="text-augustus-400">Manage your podcast host configurations</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          New Cast
        </button>
      </div>
      
      {showForm && (
        <CastForm
          cast={editingCast || undefined}
          onClose={handleFormClose}
          personalityOptions={PERSONALITY_OPTIONS}
        />
      )}
      
      {casts.length === 0 ? (
        <div className="bg-augustus-800/50 rounded-lg p-8 text-center">
          <Users className="w-12 h-12 text-augustus-500 mx-auto mb-4" />
          <p className="text-augustus-400 mb-4">No casts yet</p>
          <button
            onClick={() => setShowForm(true)}
            className="btn btn-primary"
          >
            Create Your First Cast
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
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
                  {!cast.is_default && (
                    <>
                      <button
                        onClick={() => handleEdit(cast)}
                        className="btn-icon btn btn-ghost"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(cast)}
                        className="btn-icon btn btn-ghost text-red-400 hover:text-red-300"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
              
              <div className="space-y-2">
                {cast.members.map((member, idx) => (
                  <div
                    key={member.id}
                    className="bg-augustus-900/50 rounded p-3 text-sm"
                  >
                    <div className="font-medium text-white mb-1">{member.name}</div>
                    <div className="text-augustus-400 text-xs space-y-1">
                      <div>Voice: <span className="text-augustus-300">{member.voice_id}</span></div>
                      <div>Personality: <span className="text-augustus-300">{member.personality}</span></div>
                    </div>
                  </div>
                ))}
              </div>
              
              {!cast.is_default && (
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
    </div>
  )
}

