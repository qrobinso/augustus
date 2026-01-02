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

export interface Chapter {
  title: string
  start_time: number
  end_time?: number
}

export interface BriefingCostItem {
  cost?: number
  total_tokens?: number
  characters?: number
  duration_seconds?: number
}

export interface BriefingCosts {
  story_analysis?: BriefingCostItem
  facts_gathering?: BriefingCostItem
  script_writing?: BriefingCostItem
  tts_generation?: BriefingCostItem
  total?: number
}

export interface BriefingUsage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
}

export interface BriefingExtraData {
  segment_timings?: SegmentTiming[]
  progress?: BriefingProgress | null
  cast_member_names?: Record<string, string>
  story_analysis?: string
  story_analysis_raw?: string
  facts_analysis_raw?: string
  model?: string
  usage?: BriefingUsage
  costs?: BriefingCosts
  tts_voice?: string
  stories_analyzed?: number
  stories_selected?: number
  topic_ids?: string[]
  cast_name?: string
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
  extra_data: BriefingExtraData
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
  favorite: boolean
  chapters?: Chapter[]
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
  enable_site_generation: boolean
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
  description?: string
  is_default: boolean
  members: CastMember[]
  created_at: string
  updated_at: string
}

export interface CastCreate {
  name: string
  description?: string
  members: Array<{
    name: string
    voice_id: string
    personality: string
    order: number
  }>
}

export interface CastUpdate {
  name?: string
  description?: string
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
  openrouter_writer_model?: string
  tts_provider: string
  piper_url?: string
  piper_model?: string
  elevenlabs_api_key?: string
  elevenlabs_model: string
  gemini_api_key?: string
  gemini_model: string
  enable_non_speech_sounds: boolean
  briefing_duration_minutes: number
  conversation_complexity: number
  timezone: string
  news_api_key?: string
  rss_feeds: string
  resend_api_key?: string
  resend_from_email?: string
  user_name?: string
  auto_play_next: boolean
  onboarding_completed: boolean
  onboarding_skipped: boolean
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
  list: async (
    limit = 10, 
    offset = 0, 
    listened?: boolean,
    cast_id?: string,
    topic_ids?: string[],
    favorite?: boolean
  ) => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    })
    if (listened !== undefined) {
      params.set('listened', String(listened))
    }
    if (cast_id) {
      params.set('cast_id', cast_id)
    }
    if (topic_ids && topic_ids.length > 0) {
      topic_ids.forEach(id => params.append('topic_ids', id))
    }
    if (favorite !== undefined) {
      params.set('favorite', String(favorite))
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
  
  updateFavorite: async (id: string, favorite: boolean) => {
    const { data } = await api.patch<Briefing>(`/api/briefings/${id}/favorite`, { favorite })
    return data
  },
  
  cancel: async (id: string) => {
    const { data } = await api.post<Briefing>(`/api/briefings/${id}/cancel`)
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

export interface GeneratedTopicFromPrompt {
  name: string
  description: string
  use_newsapi: boolean
  reasoning: string
  sites: Array<{
    name: string
    url: string
  }>
}

export interface TrendingTopic {
  name: string
  description: string
  color: string
  reasoning: string
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
    enable_site_generation?: boolean
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
    enable_site_generation: boolean
  }>) => {
    const { data } = await api.put<Topic>(`/api/topics/${id}`, options)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/topics/${id}`)
  },
  
  generateSites: async (topicId: string, count?: number) => {
    const params = count ? `?count=${count}` : ''
    const { data } = await api.post<{sites: Array<{name: string, url: string}>, total: number}>(`/api/topics/${topicId}/generate-sites${params}`)
    return data
  },
  
  generateFromPrompt: async (prompt: string) => {
    const { data } = await api.post<GeneratedTopicFromPrompt>('/api/topics/generate-from-prompt', { prompt })
    return data
  },
  
  generateTrending: async (count = 5) => {
    const { data } = await api.get<{ topics: TrendingTopic[] }>(
      `/api/topics/generate-trending?count=${count}`
    )
    return data.topics
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
    openrouter_writer_model: string
    tts_provider: string
    piper_url: string
    piper_model: string
    elevenlabs_api_key: string
    elevenlabs_model: string
    gemini_api_key: string
    gemini_model: string
    enable_non_speech_sounds: boolean
    briefing_duration_minutes: number
    conversation_complexity: number
    timezone: string
    news_api_key: string
    rss_feeds: string
    resend_api_key: string
    resend_from_email: string
    user_name: string
    auto_play_next: boolean
    onboarding_completed: boolean
    onboarding_skipped: boolean
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
  
  validateOpenRouterKey: async (apiKey: string) => {
    const { data } = await api.post<{ valid: boolean; message: string }>('/api/settings/validate/openrouter', { api_key: apiKey })
    return data
  },
  
  validateGeminiKey: async (apiKey: string) => {
    const { data } = await api.post<{ valid: boolean; message: string }>('/api/settings/validate/gemini', { api_key: apiKey })
    return data
  },
  
  validateElevenLabsKey: async (apiKey: string) => {
    const { data } = await api.post<{ valid: boolean; message: string }>('/api/settings/validate/elevenlabs', { api_key: apiKey })
    return data
  },
  
  restartServer: async () => {
    const { data } = await api.post<{ success: boolean; message: string }>('/api/settings/restart')
    return data
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
    cast_id?: string
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
  
  trigger: async (id: string) => {
    const { data } = await api.post<Briefing>(`/api/scheduled-briefings/${id}/trigger`)
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
  
  // Personality file management
  listPersonalityFiles: async () => {
    const { data } = await api.get<Array<{ filename: string; name: string; path: string }>>('/api/casts/personalities/files')
    return data
  },
  
  getPersonalityFile: async (filename: string) => {
    const { data } = await api.get<{ filename: string; name: string; content: string }>(`/api/casts/personalities/files/${filename}`)
    return data
  },
  
  savePersonalityFile: async (filename: string, content: string) => {
    const { data } = await api.put<{ filename: string; name: string; message: string }>(`/api/casts/personalities/files/${filename}`, { content })
    return data
  },
  
  createPersonalityFile: async (filename: string, content?: string) => {
    const { data } = await api.post<{ filename: string; name: string; message: string }>('/api/casts/personalities/files', { filename, content: content || '' })
    return data
  },
  
  deletePersonalityFile: async (filename: string) => {
    const { data } = await api.delete<{ filename: string; message: string }>(`/api/casts/personalities/files/${filename}`)
    return data
  },
  
  delete: async (id: string) => {
    await api.delete(`/api/casts/${id}`)
  },
  
  setDefault: async (id: string) => {
    const { data } = await api.post<Cast>(`/api/casts/${id}/set-default`)
    return data
  },
  
  restoreDefault: async () => {
    const { data } = await api.post<Cast>('/api/casts/default/restore')
    return data
  },
  
  getPersonalities: async () => {
    const { data } = await api.get<string[]>('/api/casts/personalities')
    return data
  },
  
  generateDescription: async (name: string, members: Array<{
    name: string
    voice_id: string
    personality: string
    order: number
  }>) => {
    const { data } = await api.post<{ description: string }>('/api/casts/generate-description', {
      name,
      members,
    })
    return data.description
  },
}

export const authApi = {
  getMe: async () => {
    const { data } = await api.get('/api/auth/me')
    return data
  },
}
