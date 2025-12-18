import { create } from 'zustand'

interface AudioState {
  currentAudio: {
    id: string
    type: 'briefing' | 'deepcast' | 'episode'
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

interface AppState extends AudioState {
  setCurrentAudio: (audio: AudioState['currentAudio']) => void
  setIsPlaying: (playing: boolean) => void
  setCurrentTime: (time: number) => void
  setDuration: (duration: number) => void
  clearAudio: () => void
}

export const useStore = create<AppState>()((set) => ({
  // Audio state
  currentAudio: null,
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  
  setCurrentAudio: (audio) => set({ 
    currentAudio: audio, 
    currentTime: audio?.initialPosition || 0 
  }),
  setIsPlaying: (playing) => set({ isPlaying: playing }),
  setCurrentTime: (time) => set({ currentTime: time }),
  setDuration: (duration) => set({ duration }),
  clearAudio: () => set({ 
    currentAudio: null, 
    isPlaying: false, 
    currentTime: 0, 
    duration: 0 
  }),
}))
