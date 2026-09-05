import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { audioManager } from '../utils/audioManager'
import { addToQueue, playNext as playNextQueue, removeFromQueue, reorderQueue, type QueueItem } from './queue'

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
  queue: QueueItem[]
  waitingForQueue: boolean
  queueFallbackSourceId: string | null
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
  addToQueue: (item: QueueItem) => void
  playNext: (item: QueueItem) => void
  removeFromQueue: (id: string) => void
  reorderQueue: (from: number, to: number) => void
  clearQueue: () => void
  updateQueueItem: (id: string, item: QueueItem) => void
  playFromQueueHead: () => boolean
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      // Profile state
      currentProfile: null,
      profiles: [],
      setCurrentProfile: (profile) => set({ currentProfile: profile, waitingForQueue: false, queueFallbackSourceId: null }),
      setProfiles: (profiles) => set({ profiles }),
      
      // Audio state
      currentAudio: null,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      audioPlayerMinimized: false,
      queue: [],
      waitingForQueue: false,
      queueFallbackSourceId: null,
  
  setCurrentAudio: (audio) => {
    // Always update the audio manager source when setting new audio
    // This ensures the correct audio is loaded even without auto-play
    if (audio?.audioUrl) {
      // Check if we need to change the source (different URL)
      const currentSrc = audioManager.src
      const newUrl = audio.audioUrl
      // Only load if it's a different source (comparing paths, not full URLs)
      if (!currentSrc || !currentSrc.endsWith(newUrl.split('/').pop() || '')) {
        audioManager.setSourceAndPlay(audio.audioUrl, false)
          .then(() => {
            // Seek to initial position if specified
            if (audio.initialPosition && audio.initialPosition > 0) {
              audioManager.seek(audio.initialPosition)
            }
          })
          .catch((error) => {
            console.warn('[Store] Failed to load audio source:', error)
          })
      }
    }
    set({ 
      currentAudio: audio, 
      waitingForQueue: false,
      queueFallbackSourceId: null,
      currentTime: audio?.initialPosition || 0 
    })
  },
  setIsPlaying: (playing) => {
    // Sync audioManager state with requested state
    if (playing && audioManager.paused) {
      audioManager.play()
        .then(() => set({ isPlaying: true }))
        .catch((error) => {
          console.warn('[Store] Failed to play in setIsPlaying:', error)
          set({ isPlaying: false })
        })
    } else if (!playing && !audioManager.paused) {
      audioManager.pause()
      set({ isPlaying: false })
    } else {
      set({ isPlaying: playing })
    }
  },
  setCurrentTime: (time) => set({ currentTime: time }),
  setDuration: (duration) => set({ duration }),
  setAudioPlayerMinimized: (minimized) => set({ audioPlayerMinimized: minimized }),
  clearAudio: () => {
    audioManager.pause()
    set({ 
      currentAudio: null, 
      isPlaying: false, 
      currentTime: 0, 
      duration: 0,
      waitingForQueue: false,
      queueFallbackSourceId: null,
    })
  },
  
  /**
   * Play audio - call this from click handlers for mobile compatibility.
   * Sets the source and starts playing synchronously.
   */
  playAudio: (audio) => {
    const { currentAudio } = get()
    const isSameAudio = currentAudio?.id === audio.id
    
    // Update state
    set({ 
      currentAudio: audio, 
      waitingForQueue: false,
      queueFallbackSourceId: null,
      currentTime: audio.initialPosition || 0,
      isPlaying: true 
    })
    
    // If it's the same audio that's already loaded, just play it
    if (isSameAudio && audioManager.src) {
      audioManager.play()
        .catch((error) => {
          console.warn('[Store] Failed to play audio:', error)
          set({ isPlaying: false })
        })
      return
    }
    
    // Load new source and play (this MUST be in the user interaction call stack)
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
    set({ waitingForQueue: false, queueFallbackSourceId: null })
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

  addToQueue: (item) => set({ queue: addToQueue(get().queue, item) }),
  playNext: (item) => set({ queue: playNextQueue(get().queue, item) }),
  removeFromQueue: (id) => {
    set({ queue: removeFromQueue(get().queue, id) })
    if (get().waitingForQueue) get().playFromQueueHead()
  },
  reorderQueue: (from, to) => {
    set({ queue: reorderQueue(get().queue, from, to) })
    if (get().waitingForQueue) get().playFromQueueHead()
  },
  clearQueue: () => set({ queue: [], waitingForQueue: false, queueFallbackSourceId: null }),
  updateQueueItem: (id, item) => {
    if (!get().queue.some(entry => entry.id === id)) return
    set({ queue: get().queue.map(entry => entry.id === id ? item : entry) })
    if (get().waitingForQueue) get().playFromQueueHead()
  },
  playFromQueueHead: () => {
    const { queue, playAudio, currentProfile } = get()
    // Failed requests stay visible for explanation/removal but never block audio.
    const head = queue.find(item => item.breakout?.status !== 'failed' &&
      (!item.breakout || item.breakout.profileId === currentProfile?.id))
    if (!head) {
      set({ waitingForQueue: false,
        queueFallbackSourceId: get().waitingForQueue ? get().currentAudio?.id ?? null : null })
      return false
    }
    if (head.breakout && head.breakout.status !== 'ready') {
      set({ waitingForQueue: true, queueFallbackSourceId: null })
      return true // Reserve play-next; do not fall through to unrelated autoplay.
    }
    set({ queue: queue.filter(item => item.id !== head.id), waitingForQueue: false })
    playAudio({ ...head, initialPosition: 0 })
    return true
  },
    }),
    {
      name: 'augustus-profile-storage',
      partialize: (state) => ({
        currentProfile: state.currentProfile,
        queue: state.queue,
      }),
      merge: (persisted, current) => {
        const saved = persisted as Partial<AppState>
        return {
          ...current,
          ...saved,
          waitingForQueue: false,
          queueFallbackSourceId: null,
          queue: (saved.queue || []).map(item => item.breakout?.status === 'requesting'
            ? { ...item, breakout: { ...item.breakout, status: 'failed' as const,
                error: 'Request interrupted. Check your briefings before trying again.' } }
            : item),
        }
      },
    }
  )
)
