import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Users,
  Loader2, 
  Plus,
  X,
  Trash2,
  ArrowLeft
} from 'lucide-react'
import { castsApi, CastCreate } from '../api/client'

const PERSONALITY_OPTIONS = [
  'Casual',
  'Professional',
  'Analytical',
  'Friendly',
  'Informative',
  'Upbeat',
  'The Provocateur/Truth-Teller',
  'The Businessman/Everyman',
  'The Scholar/Researcher',
  'The Storyteller',
  'The Skeptic',
  'The Optimist',
  'The Realist',
]

export default function CreateCast() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  const [name, setName] = useState('')
  const [members, setMembers] = useState<Array<{
    name: string
    voice_id: string
    personality: string
    order: number
  }>>([
    { name: '', voice_id: '', personality: PERSONALITY_OPTIONS[0], order: 0 },
  ])
  
  const createMutation = useMutation({
    mutationFn: (data: CastCreate) => castsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['casts'] })
      navigate('/casts')
    },
  })
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name.trim()) {
      alert('Cast name is required')
      return
    }
    
    if (members.length < 1 || members.length > 3) {
      alert('Cast must have 1-3 members')
      return
    }
    
    // Validate all members have required fields
    for (let i = 0; i < members.length; i++) {
      const member = members[i]
      if (!member.name.trim()) {
        alert(`Member ${i + 1} name is required`)
        return
      }
      if (!member.voice_id.trim()) {
        alert(`Member ${i + 1} voice ID is required`)
        return
      }
    }
    
    const castData: CastCreate = {
      name: name.trim(),
      members: members.map((m, idx) => ({
        name: m.name.trim(),
        voice_id: m.voice_id.trim(),
        personality: m.personality,
        order: idx,
      })),
    }
    
    createMutation.mutate(castData)
  }
  
  const addMember = () => {
    if (members.length < 3) {
      setMembers([
        ...members,
        {
          name: '',
          voice_id: '',
          personality: PERSONALITY_OPTIONS[0],
          order: members.length,
        },
      ])
    }
  }
  
  const removeMember = (index: number) => {
    if (members.length > 1) {
      setMembers(members.filter((_, i) => i !== index).map((m, idx) => ({ ...m, order: idx })))
    }
  }
  
  const updateMember = (index: number, field: string, value: string) => {
    const updated = [...members]
    updated[index] = { ...updated[index], [field]: value }
    setMembers(updated)
  }
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <button
          onClick={() => navigate('/casts')}
          className="flex items-center gap-2 text-augustus-400 hover:text-augustus-300 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back to Casts</span>
        </button>
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          Create New Cast
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Create a new podcast host configuration
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Cast Details */}
        <div className="card">
          <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-accent" />
            Cast Details
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="label">Cast Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Morning News Team"
                className="input"
                required
              />
            </div>
          </div>
        </div>
        
        {/* Members */}
        <div className="card">
          <div className="flex items-center justify-between mb-3 sm:mb-4">
            <h2 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
              <Users className="w-5 h-5 text-accent" />
              Members ({members.length}/3)
            </h2>
            {members.length < 3 && (
              <button
                type="button"
                onClick={addMember}
                className="btn btn-sm btn-secondary flex items-center gap-2"
                disabled={createMutation.isPending}
              >
                <Plus className="w-4 h-4" />
                Add Member
              </button>
            )}
          </div>
          
          <div className="space-y-4">
            {members.map((member, index) => (
              <div
                key={index}
                className="bg-augustus-800/50 rounded-lg p-4 border border-augustus-700"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-augustus-300">
                    Member {index + 1}
                  </span>
                  {members.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeMember(index)}
                      className="btn-icon btn btn-ghost text-red-400 hover:text-red-300"
                      disabled={createMutation.isPending}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
                
                <div className="space-y-3">
                  <div>
                    <label className="label">Name *</label>
                    <input
                      type="text"
                      value={member.name}
                      onChange={(e) => updateMember(index, 'name', e.target.value)}
                      className="input w-full"
                      placeholder="e.g., Alex"
                      required
                      disabled={createMutation.isPending}
                    />
                  </div>
                  
                  <div>
                    <label className="label">Voice ID *</label>
                    <input
                      type="text"
                      value={member.voice_id}
                      onChange={(e) => updateMember(index, 'voice_id', e.target.value)}
                      className="input w-full"
                      placeholder="e.g., 21m00Tcm4TlvDq8ikWAM"
                      required
                      disabled={createMutation.isPending}
                    />
                    <p className="text-xs text-augustus-500 mt-1">
                      Voice ID from your TTS provider (ElevenLabs, Gemini, etc.)
                    </p>
                  </div>
                  
                  <div>
                    <label className="label">Personality *</label>
                    <select
                      value={member.personality}
                      onChange={(e) => updateMember(index, 'personality', e.target.value)}
                      className="input w-full"
                      required
                      disabled={createMutation.isPending}
                    >
                      {PERSONALITY_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Create / Cancel buttons */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={!name.trim() || createMutation.isPending}
            className="btn btn-primary flex items-center justify-center gap-2"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-5 h-5" />
                Create Cast
              </>
            )}
          </button>
          <button
            type="button"
            onClick={() => navigate('/casts')}
            className="btn btn-ghost"
            disabled={createMutation.isPending}
          >
            Cancel
          </button>
        </div>
        
        {createMutation.isError && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-400">
              {(createMutation.error as Error)?.message || 'Failed to create cast'}
            </p>
          </div>
        )}
      </form>
    </div>
  )
}
