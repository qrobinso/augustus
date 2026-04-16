import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { profilesApi, Profile } from '../api/client'
import { useStore } from '../store/useStore'
import { Settings, Shield } from 'lucide-react'
import { slugify } from '../utils/profileSlug'

// Get initials from a name (max 2 characters)
function getInitials(name: string): string {
  const words = name.trim().split(/\s+/)
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
}

export default function ProfileSwitcher() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setCurrentProfile, setProfiles, profiles, clearAudio } = useStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadProfiles()
  }, [])

  const loadProfiles = async () => {
    try {
      setLoading(true)
      const data = await profilesApi.list()
      setProfiles(data.profiles)
    } catch (err) {
      console.error('Failed to load profiles:', err)
      setError('Failed to load profiles')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectProfile = (profile: Profile) => {
    // Clear any playing audio - fresh slate for each profile
    clearAudio()
    
    setCurrentProfile(profile)
    // Invalidate all profile-dependent queries to force refetch with new profile
    queryClient.invalidateQueries({ queryKey: ['briefings'] })
    queryClient.invalidateQueries({ queryKey: ['topics'] })
    queryClient.invalidateQueries({ queryKey: ['casts'] })
    queryClient.invalidateQueries({ queryKey: ['scheduled-briefings'] })
    navigate(`/${slugify(profile.name)}/dashboard`)
  }

  const handleManageProfiles = () => {
    navigate('/settings?tab=profiles')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-augustus-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-augustus-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={loadProfiles}
            className="px-4 py-2 bg-accent hover:bg-accent-600 rounded-lg text-white transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-augustus-950 flex flex-col items-center justify-center p-8 relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-augustus-900/20 via-transparent to-augustus-900/20 pointer-events-none" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-augustus-800/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center mb-12 z-10"
      >
        <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
          Who's listening?
        </h1>
        <p className="text-augustus-400">Select your profile to continue</p>
      </motion.div>

      {/* Profiles Grid */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="flex flex-wrap justify-center gap-8 z-10"
      >
        {profiles.map((profile, index) => (
          <motion.button
            key={profile.id}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.1 * index }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => handleSelectProfile(profile)}
            className="group flex flex-col items-center gap-3"
          >
            {/* Profile Avatar */}
            <div className="relative">
              <div 
                className="w-32 h-32 rounded-2xl flex items-center justify-center text-4xl font-bold text-white shadow-xl group-hover:shadow-lg transition-all duration-300 ring-4 ring-transparent group-hover:ring-accent/30"
                style={{ backgroundColor: profile.color }}
              >
                {getInitials(profile.name)}
              </div>
              {profile.is_admin && (
                <div className="absolute -top-2 -right-2 w-7 h-7 bg-accent rounded-full flex items-center justify-center shadow-lg" title="Admin">
                  <Shield className="w-4 h-4 text-white" />
                </div>
              )}
            </div>
            {/* Profile Name */}
            <span className="text-lg font-medium text-augustus-300 group-hover:text-white transition-colors">
              {profile.name}
            </span>
          </motion.button>
        ))}
      </motion.div>

      {/* Manage Profiles Button */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="mt-16 z-10"
      >
        <button
          onClick={handleManageProfiles}
          className="flex items-center gap-2 px-6 py-3 rounded-lg border border-augustus-700 text-augustus-400 hover:text-white hover:border-augustus-600 transition-all duration-200"
        >
          <Settings className="w-5 h-5" />
          <span>Manage Profiles</span>
        </button>
      </motion.div>

      {/* App Logo */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.7 }}
        className="absolute bottom-8 text-center z-10"
      >
        <p className="text-augustus-600 text-sm">
          Augustus • Audio Intelligence
        </p>
      </motion.div>
    </div>
  )
}

