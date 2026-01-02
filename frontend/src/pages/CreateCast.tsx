import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation, useParams } from 'react-router-dom'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { 
  Users,
  Loader2, 
  Plus,
  Trash2,
  ArrowLeft,
  Sparkles
} from 'lucide-react'
import clsx from 'clsx'
import { castsApi, CastCreate, CastUpdate } from '../api/client'

export default function CreateCast() {
  const navigate = useNavigate()
  const location = useLocation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  
  const isEditing = Boolean(id)
  
  // Get the previous page from location state, default to /casts
  const previousPage = (location.state as { from?: string })?.from || '/casts'
  
  const { data: personalityOptions = [], isLoading: isLoadingPersonalities } = useQuery({
    queryKey: ['personalities'],
    queryFn: () => castsApi.getPersonalities(),
  })
  
  // Fetch existing cast if editing
  const { data: existingCast, isLoading: castLoading } = useQuery({
    queryKey: ['cast', id],
    queryFn: () => castsApi.get(id!),
    enabled: isEditing,
    refetchOnMount: true, // Always refetch when component mounts to get latest data
  })
  
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isGeneratingDescription, setIsGeneratingDescription] = useState(false)
  const [members, setMembers] = useState<Array<{
    name: string
    voice_id: string
    personality: string
    order: number
  }>>([
    { name: '', voice_id: '', personality: '', order: 0 },
  ])
  // Track what we've initialized to prevent unnecessary re-initialization
  const initializedRef = useRef<{ castId?: string; dataHash?: string }>({})
  
  // Create a simple hash of the cast data to detect changes
  const getCastDataHash = (cast: typeof existingCast) => {
    if (!cast) return undefined
    const membersStr = cast.members
      .sort((a, b) => a.order - b.order)
      .map(m => `${m.name}:${m.voice_id}:${m.personality}`)
      .join('|')
    return `${cast.id}:${cast.name}:${cast.description || ''}:${membersStr}`
  }
  
  // Initialize form with existing cast data or defaults
  useEffect(() => {
    if (isEditing && existingCast && personalityOptions.length > 0) {
      const dataHash = getCastDataHash(existingCast)
      // Re-initialize if cast ID changed OR data hash changed (data was updated)
      if (initializedRef.current.castId !== existingCast.id || initializedRef.current.dataHash !== dataHash) {
        setName(existingCast.name)
        setDescription(existingCast.description || '')
        setMembers(
          existingCast.members
            .sort((a, b) => a.order - b.order)
            .map(m => {
              // If personality was deleted, fall back to the first available
              let personality = m.personality
              if (!personalityOptions.includes(m.personality)) {
                personality = personalityOptions[0]
              }
              return {
                name: m.name,
                voice_id: m.voice_id,
                personality,
                order: m.order,
              }
            })
        )
        initializedRef.current = { castId: existingCast.id, dataHash }
      }
    } else if (!isEditing && personalityOptions.length > 0) {
      // Reset when switching to create mode or initialize for first time
      if (initializedRef.current.castId !== undefined) {
        // Switching from edit to create - reset form
        setName('')
        setDescription('')
        setMembers([{ name: '', voice_id: '', personality: personalityOptions[0], order: 0 }])
        initializedRef.current = {}
      } else if (initializedRef.current.castId === undefined && initializedRef.current.dataHash === undefined) {
        // First time in create mode - initialize with default
        setMembers([{ name: '', voice_id: '', personality: personalityOptions[0], order: 0 }])
        initializedRef.current = {}
      }
    }
  }, [isEditing, existingCast, personalityOptions])
  
  const createMutation = useMutation({
    mutationFn: (data: CastCreate) => castsApi.create(data),
    onSuccess: (newCast) => {
      // Auto-select the newly created cast for briefing generation
      localStorage.setItem('selectedCastId', newCast.id)
      queryClient.invalidateQueries({ queryKey: ['casts'] })
      navigate(previousPage)
    },
  })
  
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CastUpdate }) =>
      castsApi.update(id, data),
    onSuccess: (_, variables) => {
      // Invalidate both the list and the specific cast query
      queryClient.invalidateQueries({ queryKey: ['casts'] })
      queryClient.invalidateQueries({ queryKey: ['cast', variables.id] })
      navigate(previousPage)
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
    
    if (isEditing && id) {
      // For updates, always include description (even if empty) so it can be cleared
      const updateData: CastUpdate = {
        name: name.trim(),
        description: description.trim() || '', // Send empty string to allow clearing
        members: members.map((m, idx) => ({
          name: m.name.trim(),
          voice_id: m.voice_id.trim(),
          personality: m.personality,
          order: idx,
        })),
      }
      updateMutation.mutate({ id, data: updateData })
    } else {
      // For creates, only include description if it has a value
      const createData: CastCreate = {
        name: name.trim(),
        description: description.trim() || undefined,
        members: members.map((m, idx) => ({
          name: m.name.trim(),
          voice_id: m.voice_id.trim(),
          personality: m.personality,
          order: idx,
        })),
      }
      createMutation.mutate(createData)
    }
  }
  
  const addMember = () => {
    if (members.length < 3) {
      setMembers([
        ...members,
        {
          name: '',
          voice_id: '',
          personality: personalityOptions[0] || '',
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
  
  const handleGenerateDescription = async () => {
    if (!name.trim()) {
      alert('Please enter a cast name first')
      return
    }
    
    // Validate members have required fields
    const validMembers = members.filter(m => m.name.trim() && m.personality)
    if (validMembers.length === 0) {
      alert('Please add at least one member with a name and personality')
      return
    }
    
    setIsGeneratingDescription(true)
    try {
      const generatedDescription = await castsApi.generateDescription(
        name.trim(),
        validMembers.map((m, idx) => ({
          name: m.name.trim(),
          voice_id: m.voice_id.trim(),
          personality: m.personality,
          order: idx,
        }))
      )
      setDescription(generatedDescription)
    } catch (error) {
      console.error('Failed to generate description:', error)
      alert('Failed to generate description. Please check your LLM settings.')
    } finally {
      setIsGeneratingDescription(false)
    }
  }
  
  const isLoading = createMutation.isPending || updateMutation.isPending
  
  // Show loading state while fetching existing cast
  if ((isEditing && castLoading) || isLoadingPersonalities) {
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
          onClick={() => navigate(previousPage)}
          className="flex items-center gap-2 text-augustus-400 hover:text-augustus-300 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </button>
        
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center">
            <Users className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white">
              {isEditing ? 'Edit Cast' : 'Create New Cast'}
            </h1>
            <p className="text-sm sm:text-base text-augustus-400">
              {isEditing ? 'Update your podcast host configuration' : 'Create a new podcast host configuration'}
            </p>
          </div>
        </div>
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
                disabled={isLoading}
              />
            </div>
            
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="label mb-0">
                  Description <span className="text-augustus-500 text-xs">(optional)</span>
                </label>
                <button
                  type="button"
                  onClick={handleGenerateDescription}
                  disabled={isLoading || isGeneratingDescription || !name.trim()}
                  className="btn btn-sm btn-ghost flex items-center gap-2 text-augustus-400 hover:text-augustus-300"
                  title="Generate description using AI"
                >
                  {isGeneratingDescription ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Generate
                    </>
                  )}
                </button>
              </div>
              <textarea
                value={description}
                onChange={(e) => {
                  const value = e.target.value
                  if (value.length <= 500) {
                    setDescription(value)
                  }
                }}
                className="input w-full min-h-[100px] resize-y"
                placeholder="Describe how this cast works, their dynamic, or any special instructions for the briefing writer..."
                disabled={isLoading || isGeneratingDescription}
                rows={4}
                maxLength={500}
              />
              <div className="flex items-center justify-between mt-1">
                <p className="text-xs text-augustus-500">
                  This description will be included in the briefing writer prompt to help guide how the cast discusses topics.
                </p>
                <p className={clsx(
                  "text-xs",
                  description.length > 450 ? "text-yellow-400" : "text-augustus-500"
                )}>
                  {description.length}/500
                </p>
              </div>
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
                    <label className="label">Name *</label>
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
                    <label className="label">Voice ID *</label>
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
                    <label className="label">Personality *</label>
                    <select
                      value={member.personality}
                      onChange={(e) => updateMember(index, 'personality', e.target.value)}
                      className="input w-full"
                      required
                      disabled={isLoading || isLoadingPersonalities || personalityOptions.length === 0}
                    >
                      {personalityOptions.length === 0 ? (
                        <option value="">{isLoadingPersonalities ? 'Loading personalities...' : 'No personalities available'}</option>
                      ) : (
                        personalityOptions.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Create / Cancel buttons */}
        <div className="flex flex-col-reverse sm:flex-row items-center gap-3">
          <button
            type="button"
            onClick={() => navigate(previousPage)}
            className="btn btn-ghost w-full sm:w-auto"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!name.trim() || isLoading}
            className="btn btn-primary w-full sm:w-auto flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {isEditing ? 'Updating...' : 'Creating...'}
              </>
            ) : (
              <>
                {isEditing ? 'Update Cast' : 'Create Cast'}
              </>
            )}
          </button>
        </div>
        
        {(createMutation.isError || updateMutation.isError) && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-400">
              {(createMutation.error as Error)?.message || (updateMutation.error as Error)?.message || 'Failed to save cast'}
            </p>
          </div>
        )}
      </form>
    </div>
  )
}
