import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { audioManager } from '../utils/audioManager'

// Re-export Profile type from api client for consistency
export type { Profile } from '../api/client'
import type { Profile } from '../api/client'

interface ProfileState {
  currentProfile: Profile | null
  profiles: Profile[]
  setCurrentProfile: (profile: Profile | null) => void
  setProfiles: (profiles: Profile[]) => void
}

interface AudioState {
  currentAudio: {
    id: string
    type: 'briefing'
    title: string
    audioUrl: string
    transcript?: string
    chapters?: Array<{
      title: string
      start_time: number
      end_time?: number
    }>
    initialPosition?: number  // Saved playback position to resume from
  } | null
  isPlaying: boolean
  currentTime: number
  duration: number
}

interface AppState extends AudioState, ProfileState {
  audioPlayerMinimized: boolean
  setCurrentAudio: (audio: AudioState['currentAudio']) => void
  setIsPlaying: (playing: boolean) => void
  setCurrentTime: (time: number) => void
  setDuration: (duration: number) => void
  setAudioPlayerMinimized: (minimized: boolean) => void
  clearAudio: () => void
  /**
   * Play audio synchronously - MUST be called from user interaction handler.
   * This sets the audio source and starts playing in one call, which is required
   * for mobile browsers that only allow play() in user interaction handlers.
   */
  playAudio: (audio: NonNullable<AudioState['currentAudio']>) => void
  /**
   * Toggle play/pause - MUST be called from user interaction handler.
   */
  togglePlayPause: () => void
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      // Profile state
      currentProfile: null,
      profiles: [],
      setCurrentProfile: (profile) => set({ currentProfile: profile }),
      setProfiles: (profiles) => set({ profiles }),
      
      // Audio state
      currentAudio: null,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      audioPlayerMinimized: false,
  
  setCurrentAudio: (audio) => set({ 
    currentAudio: audio, 
    currentTime: audio?.initialPosition || 0 
  }),
  setIsPlaying: (playing) => set({ isPlaying: playing }),
  setCurrentTime: (time) => set({ currentTime: time }),
  setDuration: (duration) => set({ duration }),
  setAudioPlayerMinimized: (minimized) => set({ audioPlayerMinimized: minimized }),
  clearAudio: () => {
    audioManager.pause()
    set({ 
      currentAudio: null, 
      isPlaying: false, 
      currentTime: 0, 
      duration: 0 
    })
  },
  
  /**
   * Play audio - call this from click handlers for mobile compatibility.
   * Sets the source and starts playing synchronously.
   */
  playAudio: (audio) => {
    // Update state first
    set({ 
      currentAudio: audio, 
      currentTime: audio.initialPosition || 0,
      isPlaying: true 
    })
    
    // Start playing synchronously (this MUST be in the user interaction call stack)
    audioManager.setSourceAndPlay(audio.audioUrl, true)
      .then(() => {
        // Seek to initial position if specified
        if (audio.initialPosition && audio.initialPosition > 0) {
          audioManager.seek(audio.initialPosition)
        }
      })
      .catch((error) => {
        console.warn('[Store] Failed to play audio:', error)
        set({ isPlaying: false })
      })
  },
  
  /**
   * Toggle play/pause - call this from click handlers for mobile compatibility.
   */
  togglePlayPause: () => {
    const { isPlaying, currentAudio } = get()
    
    if (!currentAudio) return
    
    if (isPlaying) {
      audioManager.pause()
      set({ isPlaying: false })
    } else {
      audioManager.play()
        .then(() => set({ isPlaying: true }))
        .catch((error) => {
          console.warn('[Store] Failed to toggle play:', error)
        })
    }
  },
    }),
    {
      name: 'augustus-profile-storage',
      partialize: (state) => ({
        currentProfile: state.currentProfile,
      }),
    }
  )
)
