import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface SegmentTiming {
  index: number
  speaker: string
  text: string
  start_seconds: number
  end_seconds: number
  duration_seconds: number
}

export interface BriefingProgress {
  step: number
  total_steps: number
  step_name: string
  percent: number
}

export interface Briefing {
  id: string
  user_id: string
  title: string
  transcript?: string
  audio_url?: string
  audio_filename?: string
  duration_seconds?: number
  cast_id?: string
  extra_data: Record<string, unknown> & {
    segment_timings?: SegmentTiming[]
    progress?: BriefingProgress | null
  }
  sources: Array<{
    title: string
    url: string
    summary?: string
  }>
  status: 'pending' | 'generating' | 'completed' | 'failed' | 'cancelled'
  error_message?: string
  generated_at?: string
  created_at: string
  listened: boolean
  listened_at?: string
  playback_position?: number
}

export interface DeepCast {
  id: string
  user_id: string
  query: string
  title?: string
  transcript?: string
  cast_id?: string
  chapters: Array<{
    title: string
    start_time: number
    end_time?: number
  }>
  audio_url?: string
  audio_filename?: string
  duration_seconds?: number
  sources: Array<{
    title: string
    url: string
    snippet?: string
  }>
  extra_data: Record<string, unknown>
  status: 'pending' | 'researching' | 'generating' | 'completed' | 'failed'
  error_message?: string
  created_at: string
  completed_at?: string
}

export interface Episode {
  id: string
  station_id: string
  title: string
  summary?: string
  transcript?: string
  audio_url?: string
  audio_filename?: string
  duration_seconds?: number
  sources: Array<Record<string, unknown>>
  extra_data: Record<string, unknown>
  status: string
  created_at: string
}

export interface Station {
  id: string
  user_id: string
  topic: string
  description?: string
  cast_id?: string
  update_frequency_hours: number
  settings: Record<string, unknown>
  is_active: boolean
  last_update?: string
  created_at: string
  episodes: Episode[]
  episode_count: number
}

export interface Topic {
  id: string
  user_id: string
  name: string
  slug: string
  description?: string
  color?: string
  is_active: boolean
  use_newsapi: boolean
  created_at: string
  site_count: number
}

export interface CustomSite {
  id: string
  user_id: string
  name: string
  url: string
  topic_id: string
  topic_name?: string
  topic_color?: string
  is_active: boolean
  last_fetched?: string
  last_error?: string
  created_at: string
}

export interface CustomSiteTestResult {
  success: boolean
  articles_found: number
  articles: Array<{
    title: string
    url: string
    summary?: string
  }>
  error?: string
}

export interface CastMember {
  id: string
  cast_id: string
  name: string
  voice_id: string
  personality: string
  order: number
  created_at: string
}

export interface Cast {
  id: string
  user_id: string
  name: string
  is_default: boolean
  members: CastMember[]
  created_at: string
  updated_at: string
}

export interface CastCreate {
  name: string
  members: Array<{
    name: string
    voice_id: string
    personality: string
    order: number
  }>
}

export interface CastUpdate {
  name?: string
  members?: Array<{
    name: string
    voice_id: string
    personality: string
    order: number
  }>
}

export interface AppSettings {
  openrouter_api_key?: string
  openrouter_model: string
  tts_provider: string
  elevenlabs_api_key?: string
  elevenlabs_model: string
  gemini_api_key?: string
  gemini_model: string
  tts_voice_host1: string
  tts_voice_host2: string
  briefing_duration_minutes: number
  deepcast_duration_minutes: number
  station_update_duration_minutes: number
  conversation_complexity: number
  timezone: string
  news_api_key?: string
  rss_feeds: string
  resend_api_key?: string
  user_name?: string
  openrouter_configured: boolean
  elevenlabs_configured: boolean
  news_api_configured: boolean
  resend_configured: boolean
  gemini_configured: boolean
}

export interface TimezoneOption {
  id: string
  name: string
  offset: string
}

export interface TimezoneGroups {
  [region: string]: TimezoneOption[]
}

export interface ScheduledBriefing {
  id: string
  user_id: string
  name: string
  topic_ids: string[]
  cast_id?: string
  schedule_time: string
  schedule_days: number[]
  notification_methods: string[]
  email_recipients: string[]
  webhook_url?: string
  is_active: boolean
  max_duration_minutes: number
  resend_api_key?: string
  last_generated_at?: string
  created_at: string
  updated_at: string
}

export interface ModelOption {
  id: string
  name: string
  provider: string
  context_length?: number
  pricing?: {
    prompt: number
    completion: number
  }
  description?: string
}

// API functions
export const briefingsApi = {
  list: async (limit = 10, offset = 0, listened?: boolean) => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    })
    if (listened !== undefined) {
      params.set('listened', String(listened))
    }
    const { data } = await api.get<{ briefings: Briefing[]; total: number }>(
      `/api/briefings?${params}`
    )
    return data
  },
  
  get: async (id: string) => {
    const { data } = await api.get<Briefing>(`/api/briefings/${id}`)
    return data
  },
  
  generate: async (options: {
    topic_ids?: string[]
    max_duration_minutes?: number
    cast_id?: string
  } = {}) => {
    const { data } = await api.post<Briefing>('/api/briefings/generate', options)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/briefings/${id}`)
  },
  
  updateListened: async (id: string, listened: boolean) => {
    const { data } = await api.patch<Briefing>(`/api/briefings/${id}/listened`, { listened })
    return data
  },
  
  updatePlaybackPosition: async (id: string, position: number) => {
    const { data } = await api.patch<Briefing>(`/api/briefings/${id}/playback-position`, { position })
    return data
  },
  
  cancel: async (id: string) => {
    const { data } = await api.post<Briefing>(`/api/briefings/${id}/cancel`)
    return data
  },
}

export const deepcastsApi = {
  list: async (limit = 10, offset = 0) => {
    const { data } = await api.get<{ deepcasts: DeepCast[]; total: number }>(
      `/api/deepcasts?limit=${limit}&offset=${offset}`
    )
    return data
  },
  
  get: async (id: string) => {
    const { data } = await api.get<DeepCast>(`/api/deepcasts/${id}`)
    return data
  },
  
  create: async (options: {
    query: string
    target_duration_minutes?: number
    num_sources?: number
    cast_id?: string
  }) => {
    const { data } = await api.post<DeepCast>('/api/deepcasts', options)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/deepcasts/${id}`)
  },
}

export const stationsApi = {
  list: async (limit = 10, offset = 0) => {
    const { data } = await api.get<{ stations: Station[]; total: number }>(
      `/api/stations?limit=${limit}&offset=${offset}`
    )
    return data
  },
  
  get: async (id: string) => {
    const { data } = await api.get<Station>(`/api/stations/${id}`)
    return data
  },
  
  create: async (options: {
    topic: string
    description?: string
    update_frequency_hours?: number
    cast_id?: string
  }) => {
    const { data } = await api.post<Station>('/api/stations', options)
    return data
  },
  
  update: async (id: string, options: Partial<{
    topic: string
    description: string
    update_frequency_hours: number
    is_active: boolean
    cast_id: string
  }>) => {
    const { data } = await api.put<Station>(`/api/stations/${id}`, options)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/stations/${id}`)
  },
  
  generateEpisode: async (id: string, force = false) => {
    const { data } = await api.post(`/api/stations/${id}/episodes?force=${force}`)
    return data
  },
  
  listEpisodes: async (id: string, limit = 10, offset = 0) => {
    const { data } = await api.get<Episode[]>(
      `/api/stations/${id}/episodes?limit=${limit}&offset=${offset}`
    )
    return data
  },
}

export const customSitesApi = {
  list: async (topicId?: string, limit = 50, offset = 0) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (topicId) params.set('topic_id', topicId)
    const { data } = await api.get<{ sites: CustomSite[]; total: number }>(
      `/api/custom-sites?${params}`
    )
    return data
  },
  
  get: async (id: string) => {
    const { data } = await api.get<CustomSite>(`/api/custom-sites/${id}`)
    return data
  },
  
  create: async (options: {
    name: string
    url: string
    topic_id: string
  }) => {
    const { data } = await api.post<CustomSite>('/api/custom-sites', options)
    return data
  },
  
  update: async (id: string, options: Partial<{
    name: string
    url: string
    topic_id: string
    is_active: boolean
  }>) => {
    const { data } = await api.put<CustomSite>(`/api/custom-sites/${id}`, options)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/custom-sites/${id}`)
  },
  
  test: async (id: string) => {
    const { data } = await api.post<CustomSiteTestResult>(`/api/custom-sites/${id}/test`)
    return data
  },
}

export const topicsApi = {
  list: async (includeInactive = false) => {
    const params = new URLSearchParams()
    if (includeInactive) params.set('include_inactive', 'true')
    const { data } = await api.get<{ topics: Topic[]; total: number }>(
      `/api/topics?${params}`
    )
    return data
  },
  
  get: async (id: string) => {
    const { data } = await api.get<Topic>(`/api/topics/${id}`)
    return data
  },
  
  create: async (options: {
    name: string
    description?: string
    color?: string
    use_newsapi?: boolean
  }) => {
    const { data } = await api.post<Topic>('/api/topics', options)
    return data
  },
  
  update: async (id: string, options: Partial<{
    name: string
    description: string
    color: string
    is_active: boolean
    use_newsapi: boolean
  }>) => {
    const { data } = await api.put<Topic>(`/api/topics/${id}`, options)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/topics/${id}`)
  },
}

export const settingsApi = {
  get: async () => {
    const { data } = await api.get<AppSettings>('/api/settings')
    return data
  },
  
  update: async (settings: Partial<{
    openrouter_api_key: string
    openrouter_model: string
    tts_provider: string
    elevenlabs_api_key: string
    gemini_api_key: string
    gemini_model: string
    tts_voice_host1: string
    tts_voice_host2: string
    briefing_duration_minutes: number
    deepcast_duration_minutes: number
    station_update_duration_minutes: number
    conversation_complexity: number
    timezone: string
    news_api_key: string
    rss_feeds: string
    resend_api_key: string
    user_name: string
  }>) => {
    const { data } = await api.put<AppSettings>('/api/settings', settings)
    return data
  },
  
  getModels: async () => {
    const { data } = await api.get<{ models: ModelOption[] }>('/api/settings/models')
    return data.models
  },
  
  getTimezones: async () => {
    const { data } = await api.get<{ timezones: TimezoneGroups }>('/api/settings/timezones')
    return data.timezones
  },
}

export const scheduledBriefingsApi = {
  list: async (limit = 50, offset = 0) => {
    const { data } = await api.get<{ scheduled_briefings: ScheduledBriefing[]; total: number }>(
      `/api/scheduled-briefings?limit=${limit}&offset=${offset}`
    )
    return data
  },
  
  get: async (id: string) => {
    const { data } = await api.get<ScheduledBriefing>(`/api/scheduled-briefings/${id}`)
    return data
  },
  
  create: async (options: {
    name: string
    topic_ids?: string[]
    schedule_time: string
    schedule_days: number[]
    notification_methods: string[]
    email_recipients?: string[]
    webhook_url?: string
    is_active?: boolean
    max_duration_minutes?: number
    resend_api_key?: string
  }) => {
    const { data } = await api.post<ScheduledBriefing>('/api/scheduled-briefings', options)
    return data
  },
  
  update: async (id: string, options: Partial<{
    name: string
    topic_ids: string[]
    schedule_time: string
    schedule_days: number[]
    notification_methods: string[]
    email_recipients: string[]
    webhook_url: string
    is_active: boolean
    max_duration_minutes: number
    resend_api_key: string
  }>) => {
    const { data } = await api.put<ScheduledBriefing>(`/api/scheduled-briefings/${id}`, options)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/scheduled-briefings/${id}`)
  },
  
  toggle: async (id: string) => {
    const { data } = await api.patch<ScheduledBriefing>(`/api/scheduled-briefings/${id}/toggle`)
    return data
  },
}

export const castsApi = {
  list: async () => {
    const { data } = await api.get<{ casts: Cast[] }>('/api/casts')
    return data
  },
  
  get: async (id: string) => {
    const { data } = await api.get<Cast>(`/api/casts/${id}`)
    return data
  },
  
  create: async (cast: CastCreate) => {
    const { data } = await api.post<Cast>('/api/casts', cast)
    return data
  },
  
  update: async (id: string, cast: CastUpdate) => {
    const { data } = await api.put<Cast>(`/api/casts/${id}`, cast)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/casts/${id}`)
  },
  
  setDefault: async (id: string) => {
    const { data } = await api.post<Cast>(`/api/casts/${id}/set-default`)
    return data
  },
}

export const authApi = {
  getMe: async () => {
    const { data } = await api.get('/api/auth/me')
    return data
  },
}
