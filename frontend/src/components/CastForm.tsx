import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Plus, Trash2, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { castsApi, Cast, CastCreate, CastUpdate } from '../api/client'

interface CastFormProps {
  cast?: Cast
  onClose: () => void
  personalityOptions: string[]
}

export default function CastForm({ cast, onClose, personalityOptions }: CastFormProps) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [members, setMembers] = useState<Array<{
    name: string
    voice_id: string
    personality: string
    order: number
  }>>([
    { name: '', voice_id: '', personality: personalityOptions[0], order: 0 },
  ])
  
  useEffect(() => {
    if (cast) {
      setName(cast.name)
      setMembers(
        cast.members
          .sort((a, b) => a.order - b.order)
          .map(m => ({
            name: m.name,
            voice_id: m.voice_id,
            personality: m.personality,
            order: m.order,
          }))
      )
    }
  }, [cast])
  
  const createMutation = useMutation({
    mutationFn: (data: CastCreate) => castsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['casts'] })
      onClose()
    },
  })
  
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CastUpdate }) =>
      castsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['casts'] })
      onClose()
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
    
    const castData = {
      name: name.trim(),
      members: members.map((m, idx) => ({
        name: m.name.trim(),
        voice_id: m.voice_id.trim(),
        personality: m.personality,
        order: idx,
      })),
    }
    
    if (cast) {
      updateMutation.mutate({ id: cast.id, data: castData })
    } else {
      createMutation.mutate(castData)
    }
  }
  
  const addMember = () => {
    if (members.length < 3) {
      setMembers([
        ...members,
        {
          name: '',
          voice_id: '',
          personality: personalityOptions[0],
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
  
  const isLoading = createMutation.isPending || updateMutation.isPending
  
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-augustus-900 rounded-lg border border-augustus-800 w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="sticky top-0 bg-augustus-900 border-b border-augustus-800 p-6 flex items-center justify-between">
          <h2 className="text-xl font-bold text-white">
            {cast ? 'Edit Cast' : 'Create Cast'}
          </h2>
          <button
            onClick={onClose}
            className="btn-icon btn btn-ghost"
            disabled={isLoading}
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-augustus-300 mb-2">
              Cast Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input w-full"
              placeholder="e.g., Morning News Team"
              required
              disabled={isLoading}
            />
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="block text-sm font-medium text-augustus-300">
                Members ({members.length}/3)
              </label>
              {members.length < 3 && (
                <button
                  type="button"
                  onClick={addMember}
                  className="btn btn-sm btn-ghost flex items-center gap-2"
                  disabled={isLoading}
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
                        disabled={isLoading}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                  
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs text-augustus-400 mb-1">
                        Name
                      </label>
                      <input
                        type="text"
                        value={member.name}
                        onChange={(e) => updateMember(index, 'name', e.target.value)}
                        className="input w-full"
                        placeholder="e.g., Alex"
                        required
                        disabled={isLoading}
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs text-augustus-400 mb-1">
                        Voice ID
                      </label>
                      <input
                        type="text"
                        value={member.voice_id}
                        onChange={(e) => updateMember(index, 'voice_id', e.target.value)}
                        className="input w-full"
                        placeholder="e.g., 21m00Tcm4TlvDq8ikWAM"
                        required
                        disabled={isLoading}
                      />
                      <p className="text-xs text-augustus-500 mt-1">
                        Voice ID from your TTS provider (ElevenLabs, Gemini, etc.)
                      </p>
                    </div>
                    
                    <div>
                      <label className="block text-xs text-augustus-400 mb-1">
                        Personality
                      </label>
                      <select
                        value={member.personality}
                        onChange={(e) => updateMember(index, 'personality', e.target.value)}
                        className="input w-full"
                        required
                        disabled={isLoading}
                      >
                        {personalityOptions.map((opt) => (
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
          
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-augustus-800">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-ghost"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {cast ? 'Updating...' : 'Creating...'}
                </>
              ) : (
                cast ? 'Update Cast' : 'Create Cast'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

