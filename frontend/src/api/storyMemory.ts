import { api } from './client'

export type StoryPreference = 'normal' | 'follow' | 'less'

export interface EvidenceClaim {
  text: string
  attribution: 'supported' | 'unverified'
  found_by: string[]
  sources: Array<{ url: string; title: string; excerpt: string }>
}

export interface StoryChapter {
  story_id: string
  title: string
  development: string
  change_type: 'new' | 'update' | 'unchanged'
  preference: StoryPreference
  claims: EvidenceClaim[]
}

export interface StoryState {
  id: string
  title: string
  preference: StoryPreference
}

export const storyMemoryApi = {
  get: async (id: string, profileId: string) => {
    const { data } = await api.get<StoryState>(`/api/stories/${encodeURIComponent(id)}`, {
      headers: { 'X-Profile-ID': profileId },
    })
    return data
  },
  setPreference: async (id: string, profileId: string, preference: StoryPreference) => {
    const { data } = await api.patch<{ preference: StoryPreference }>(
      `/api/stories/${encodeURIComponent(id)}/preference`,
      { preference },
      { headers: { 'X-Profile-ID': profileId } },
    )
    return data
  },
}
