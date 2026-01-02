/**
 * Global Audio Manager
 * 
 * Provides a singleton audio element that persists across the app lifecycle.
 * This is critical for mobile browsers which require audio.play() to be called
 * synchronously within a user interaction event handler.
 * 
 * By having the audio element exist BEFORE the user clicks, we can call play()
 * directly in click handlers from any component.
 */

class AudioManager {
  private audio: HTMLAudioElement | null = null
  private onTimeUpdateCallbacks: Set<(time: number) => void> = new Set()
  private onDurationChangeCallbacks: Set<(duration: number) => void> = new Set()
  private onEndedCallbacks: Set<() => void> = new Set()
  private onPlayCallbacks: Set<() => void> = new Set()
  private onPauseCallbacks: Set<() => void> = new Set()
  private onErrorCallbacks: Set<(error: Error) => void> = new Set()

  constructor() {
    // Create audio element immediately (before any user interaction)
    if (typeof window !== 'undefined') {
      this.initAudio()
    }
  }

  private initAudio() {
    this.audio = new Audio()
    this.audio.preload = 'auto'
    // @ts-ignore - playsInline is valid but TypeScript doesn't know about it
    this.audio.playsInline = true
    
    // Set up event listeners
    this.audio.addEventListener('timeupdate', () => {
      this.onTimeUpdateCallbacks.forEach(cb => cb(this.audio!.currentTime))
    })
    
    this.audio.addEventListener('durationchange', () => {
      this.onDurationChangeCallbacks.forEach(cb => cb(this.audio!.duration))
    })
    
    this.audio.addEventListener('ended', () => {
      this.onEndedCallbacks.forEach(cb => cb())
    })
    
    this.audio.addEventListener('play', () => {
      this.onPlayCallbacks.forEach(cb => cb())
    })
    
    this.audio.addEventListener('pause', () => {
      this.onPauseCallbacks.forEach(cb => cb())
    })
    
    this.audio.addEventListener('error', () => {
      const error = new Error(`Audio error: ${this.audio?.error?.message || 'Unknown error'}`)
      this.onErrorCallbacks.forEach(cb => cb(error))
    })
  }

  getAudioElement(): HTMLAudioElement | null {
    return this.audio
  }

  /**
   * Set the audio source and optionally start playing.
   * MUST be called from within a user interaction handler for mobile compatibility.
   */
  setSourceAndPlay(url: string, autoplay: boolean = true): Promise<void> {
    if (!this.audio) {
      return Promise.reject(new Error('Audio element not initialized'))
    }

    this.audio.src = url
    this.audio.load()

    if (autoplay) {
      return this.audio.play().catch(error => {
        console.warn('[AudioManager] Play failed:', error)
        throw error
      })
    }

    return Promise.resolve()
  }

  /**
   * Play the current audio.
   * MUST be called from within a user interaction handler for mobile compatibility.
   */
  play(): Promise<void> {
    if (!this.audio) {
      return Promise.reject(new Error('Audio element not initialized'))
    }
    return this.audio.play()
  }

  pause(): void {
    this.audio?.pause()
  }

  seek(time: number): void {
    if (this.audio) {
      this.audio.currentTime = time
    }
  }

  setVolume(volume: number): void {
    if (this.audio) {
      this.audio.volume = Math.max(0, Math.min(1, volume))
    }
  }

  setPlaybackRate(rate: number): void {
    if (this.audio) {
      this.audio.playbackRate = rate
    }
  }

  get currentTime(): number {
    return this.audio?.currentTime || 0
  }

  get duration(): number {
    return this.audio?.duration || 0
  }

  get paused(): boolean {
    return this.audio?.paused ?? true
  }

  get readyState(): number {
    return this.audio?.readyState ?? 0
  }

  get src(): string {
    return this.audio?.src || ''
  }

  // Event subscription methods
  onTimeUpdate(callback: (time: number) => void): () => void {
    this.onTimeUpdateCallbacks.add(callback)
    return () => this.onTimeUpdateCallbacks.delete(callback)
  }

  onDurationChange(callback: (duration: number) => void): () => void {
    this.onDurationChangeCallbacks.add(callback)
    return () => this.onDurationChangeCallbacks.delete(callback)
  }

  onEnded(callback: () => void): () => void {
    this.onEndedCallbacks.add(callback)
    return () => this.onEndedCallbacks.delete(callback)
  }

  onPlay(callback: () => void): () => void {
    this.onPlayCallbacks.add(callback)
    return () => this.onPlayCallbacks.delete(callback)
  }

  onPause(callback: () => void): () => void {
    this.onPauseCallbacks.add(callback)
    return () => this.onPauseCallbacks.delete(callback)
  }

  onError(callback: (error: Error) => void): () => void {
    this.onErrorCallbacks.add(callback)
    return () => this.onErrorCallbacks.delete(callback)
  }
}

// Export singleton instance
export const audioManager = new AudioManager()


