import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Plus, 
  Trash2, 
  Pencil, 
  Loader2, 
  AlertCircle,
  Check,
  X,
  Shield
} from 'lucide-react'
import clsx from 'clsx'
import { profilesApi, Profile } from '../api/client'
import { useStore } from '../store/useStore'

// Profile name length limit (used in generation, keep it reasonable)
const PROFILE_NAME_MAX_LENGTH = 50

// Preset colors for profiles
const PROFILE_COLORS = [
  '#e85d04', // App accent color (orange)
  '#8B5CF6', // Violet
  '#6366F1', // Indigo
  '#3B82F6', // Blue
  '#0EA5E9', // Sky
  '#14B8A6', // Teal
  '#10B981', // Emerald
  '#22C55E', // Green
  '#84CC16', // Lime
  '#EAB308', // Yellow
  '#F59E0B', // Amber
  '#F97316', // Orange
  '#EF4444', // Red
  '#EC4899', // Pink
  '#D946EF', // Fuchsia
  '#64748B', // Slate
]

// Get initials from a name (max 2 characters)
function getInitials(name: string): string {
  const words = name.trim().split(/\s+/)
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
}

interface EditingProfile {
  id: string
  name: string
  color: string
}

export default function ProfileManagement() {
  const queryClient = useQueryClient()
  const { currentProfile, setCurrentProfile, setProfiles } = useStore()
  
  const [isCreating, setIsCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState('#e85d04')  // App accent color
  const [showColorPicker, setShowColorPicker] = useState(false)
  const [editingProfile, setEditingProfile] = useState<EditingProfile | null>(null)
  const [showEditColorPicker, setShowEditColorPicker] = useState(false)
  
  // Fetch profiles
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['profiles'],
    queryFn: () => profilesApi.list(),
  })
  
  // Create profile mutation
  const createMutation = useMutation({
    mutationFn: profilesApi.create,
    onSuccess: (newProfile) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      setProfiles([...(data?.profiles || []), newProfile])
      setIsCreating(false)
      setNewName('')
      setNewColor('#e85d04')  // App accent color
    },
  })
  
  // Update profile mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; name?: string; color?: string }) =>
      profilesApi.update(id, data),
    onSuccess: (updatedProfile) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      // Update store if this is the current profile
      if (currentProfile?.id === updatedProfile.id) {
        setCurrentProfile(updatedProfile)
      }
      setEditingProfile(null)
    },
  })
  
  // Delete profile mutation
  const deleteMutation = useMutation({
    mutationFn: profilesApi.delete,
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      // If deleted current profile, switch to another
      if (currentProfile?.id === deletedId) {
        const remaining = data?.profiles.filter(p => p.id !== deletedId) || []
        setCurrentProfile(remaining[0] || null)
      }
    },
  })
  
  const handleCreate = () => {
    if (!newName.trim()) return
    if (newName.trim().length > PROFILE_NAME_MAX_LENGTH) return
    createMutation.mutate({ name: newName.trim(), color: newColor })
  }
  
  const handleUpdate = () => {
    if (!editingProfile || !editingProfile.name.trim()) return
    if (editingProfile.name.trim().length > PROFILE_NAME_MAX_LENGTH) return
    updateMutation.mutate({
      id: editingProfile.id,
      name: editingProfile.name.trim(),
      color: editingProfile.color,
    })
  }
  
  const handleDelete = (profile: Profile) => {
    if (data?.profiles.length === 1) {
      alert('You must have at least one profile.')
      return
    }
    if (confirm(`Are you sure you want to delete "${profile.name}"? All data associated with this profile will be lost.`)) {
      deleteMutation.mutate(profile.id)
    }
  }
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <p className="text-augustus-400 mb-4">Failed to load profiles</p>
        <button onClick={() => refetch()} className="btn btn-primary">
          Retry
        </button>
      </div>
    )
  }
  
  const profiles = data?.profiles || []
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Profiles</h2>
          <p className="text-sm text-augustus-400">
            Manage user profiles with separate briefings, topics, and schedules
          </p>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          disabled={isCreating}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Profile
        </button>
      </div>
      
      {/* Create Profile Form */}
      <AnimatePresence>
        {isCreating && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="card bg-augustus-800/50 border-accent/30">
              <h3 className="text-base font-medium text-white mb-4">Create New Profile</h3>
              <div className="flex items-start gap-4">
                {/* Color Picker */}
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowColorPicker(!showColorPicker)}
                    className="w-16 h-16 rounded-xl flex items-center justify-center text-xl font-bold text-white shadow-lg hover:opacity-90 transition-all"
                    style={{ backgroundColor: newColor }}
                  >
                    {newName ? getInitials(newName) : '?'}
                  </button>
                  
                  {showColorPicker && (
                    <>
                      <div 
                        className="fixed inset-0 z-40" 
                        onClick={() => setShowColorPicker(false)} 
                      />
                      <div className="absolute top-full left-0 mt-2 p-3 bg-augustus-900 border border-augustus-700 rounded-xl shadow-xl z-50 w-48">
                        <p className="text-xs text-augustus-400 mb-2">Choose color</p>
                        <div className="grid grid-cols-4 gap-2">
                          {PROFILE_COLORS.map((color) => (
                            <button
                              key={color}
                              type="button"
                              onClick={() => {
                                setNewColor(color)
                                setShowColorPicker(false)
                              }}
                              className={clsx(
                                'w-9 h-9 rounded-lg transition-all',
                                newColor === color && 'ring-2 ring-white ring-offset-2 ring-offset-augustus-900'
                              )}
                              style={{ backgroundColor: color }}
                            />
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
                
                {/* Name Input */}
                <div className="flex-1">
                  <label className="block text-xs text-augustus-400 mb-1">
                    Name (used in briefings)
                    <span className="ml-1 text-augustus-500">
                      ({newName.length}/{PROFILE_NAME_MAX_LENGTH})
                    </span>
                  </label>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => {
                      if (e.target.value.length <= PROFILE_NAME_MAX_LENGTH) {
                        setNewName(e.target.value)
                      }
                    }}
                    placeholder="e.g. John"
                    maxLength={PROFILE_NAME_MAX_LENGTH}
                    className={`input w-full ${newName.length > PROFILE_NAME_MAX_LENGTH ? 'border-red-500' : ''}`}
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreate()
                      if (e.key === 'Escape') setIsCreating(false)
                    }}
                  />
                  {newName.length > PROFILE_NAME_MAX_LENGTH && (
                    <p className="text-xs text-red-400 mt-1">
                      Name must be {PROFILE_NAME_MAX_LENGTH} characters or less
                    </p>
                  )}
                </div>
                
                {/* Actions */}
                <div className="flex items-center gap-2 pt-5">
                  <button
                    onClick={handleCreate}
                    disabled={!newName.trim() || newName.trim().length > PROFILE_NAME_MAX_LENGTH || createMutation.isPending}
                    className="btn btn-primary p-2"
                  >
                    {createMutation.isPending ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Check className="w-5 h-5" />
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setIsCreating(false)
                      setNewName('')
                      setNewColor('#e85d04')  // App accent color
                    }}
                    className="btn btn-ghost p-2"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Profiles List */}
      <div className="space-y-3">
        {profiles.map((profile) => (
          <div
            key={profile.id}
            className={clsx(
              'card flex items-center gap-4 transition-colors',
              currentProfile?.id === profile.id && 'border-accent/50 bg-accent/5'
            )}
          >
            {editingProfile?.id === profile.id ? (
              <>
                {/* Edit Mode */}
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowEditColorPicker(!showEditColorPicker)}
                    className="w-14 h-14 rounded-xl flex items-center justify-center text-lg font-bold text-white shadow-lg hover:opacity-90 transition-all"
                    style={{ backgroundColor: editingProfile.color }}
                  >
                    {getInitials(editingProfile.name || profile.name)}
                  </button>
                  
                  {showEditColorPicker && (
                    <>
                      <div 
                        className="fixed inset-0 z-40" 
                        onClick={() => setShowEditColorPicker(false)} 
                      />
                      <div className="absolute top-full left-0 mt-2 p-3 bg-augustus-900 border border-augustus-700 rounded-xl shadow-xl z-50 w-48">
                        <p className="text-xs text-augustus-400 mb-2">Choose color</p>
                        <div className="grid grid-cols-4 gap-2">
                          {PROFILE_COLORS.map((color) => (
                            <button
                              key={color}
                              type="button"
                              onClick={() => {
                                setEditingProfile({ ...editingProfile, color })
                                setShowEditColorPicker(false)
                              }}
                              className={clsx(
                                'w-9 h-9 rounded-lg transition-all',
                                editingProfile.color === color && 'ring-2 ring-white ring-offset-2 ring-offset-augustus-900'
                              )}
                              style={{ backgroundColor: color }}
                            />
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
                
                <div className="flex-1">
                  <label className="block text-xs text-augustus-400 mb-1">
                    Name (used in briefings)
                    <span className="ml-1 text-augustus-500">
                      ({editingProfile.name.length}/{PROFILE_NAME_MAX_LENGTH})
                    </span>
                  </label>
                  <input
                    type="text"
                    value={editingProfile.name}
                    onChange={(e) => {
                      if (e.target.value.length <= PROFILE_NAME_MAX_LENGTH) {
                        setEditingProfile({ ...editingProfile, name: e.target.value })
                      }
                    }}
                    maxLength={PROFILE_NAME_MAX_LENGTH}
                    className={`input w-full ${editingProfile.name.length > PROFILE_NAME_MAX_LENGTH ? 'border-red-500' : ''}`}
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleUpdate()
                      if (e.key === 'Escape') setEditingProfile(null)
                    }}
                  />
                  {editingProfile.name.length > PROFILE_NAME_MAX_LENGTH && (
                    <p className="text-xs text-red-400 mt-1">
                      Name must be {PROFILE_NAME_MAX_LENGTH} characters or less
                    </p>
                  )}
                </div>
                
                <div className="flex items-center gap-2 pt-5">
                  <button
                    onClick={handleUpdate}
                    disabled={!editingProfile.name.trim() || editingProfile.name.trim().length > PROFILE_NAME_MAX_LENGTH || updateMutation.isPending}
                    className="btn btn-primary p-2"
                  >
                    {updateMutation.isPending ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Check className="w-5 h-5" />
                    )}
                  </button>
                  <button
                    onClick={() => setEditingProfile(null)}
                    className="btn btn-ghost p-2"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </>
            ) : (
              <>
                {/* View Mode */}
                <div 
                  className="w-14 h-14 rounded-xl flex items-center justify-center text-lg font-bold text-white shadow-lg"
                  style={{ backgroundColor: profile.color }}
                >
                  {getInitials(profile.name)}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-white truncate">{profile.name}</h3>
                    {profile.is_admin && (
                      <span className="text-xs px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded-full flex items-center gap-1">
                        <Shield className="w-3 h-3" />
                        Admin
                      </span>
                    )}
                    {currentProfile?.id === profile.id && (
                      <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded-full">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-augustus-500">
                    Created {new Date(profile.created_at).toLocaleDateString()}
                  </p>
                </div>
                
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setEditingProfile({
                      id: profile.id,
                      name: profile.name,
                      color: profile.color,
                    })}
                    className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
                    title="Edit"
                  >
                    <Pencil className="w-5 h-5" />
                  </button>
                  {!profile.is_admin && (
                    <button
                      onClick={() => handleDelete(profile)}
                      disabled={deleteMutation.isPending}
                      className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                      title="Delete"
                    >
                      {deleteMutation.isPending ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <Trash2 className="w-5 h-5" />
                      )}
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
      
      {profiles.length === 0 && !isCreating && (
        <div className="text-center py-12">
          <p className="text-augustus-400 mb-4">No profiles found. Create one to get started.</p>
          <button onClick={() => setIsCreating(true)} className="btn btn-primary">
            Create Profile
          </button>
        </div>
      )}
    </div>
  )
}
