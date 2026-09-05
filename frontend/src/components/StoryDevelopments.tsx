import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, BellOff, ExternalLink, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { storyMemoryApi, type StoryChapter, type StoryPreference, type StoryState } from '../api/storyMemory'
import { useStore } from '../store/useStore'

const changeLabels = { new: 'New story', update: 'New development', unchanged: 'Catch up' }

function StoryCard({ story, profileId }: { story: StoryChapter; profileId: string }) {
  const queryClient = useQueryClient()
  const queryKey = ['story-memory', profileId, story.story_id]
  const current = useQuery({
    queryKey,
    queryFn: () => storyMemoryApi.get(story.story_id, profileId),
  })
  const preference = current.data?.preference ?? story.preference
  const update = useMutation({
    mutationFn: (next: StoryPreference) => storyMemoryApi.setPreference(story.story_id, profileId, next),
    onSuccess: ({ preference: next }) => {
      queryClient.setQueryData<StoryState>(queryKey, { id: story.story_id, title: story.title, preference: next })
    },
  })
  const busy = update.isPending || current.isPending || current.isError
  const claims = story.claims ?? []
  return (
    <article className="rounded-xl border border-augustus-700/60 p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs mb-2">
        <span className={clsx('rounded-full px-2.5 py-1', story.change_type === 'update'
          ? 'bg-accent/10 text-accent' : 'bg-augustus-800 text-augustus-300')}>
          {changeLabels[story.change_type] ?? 'Story'}
        </span>
        {preference === 'follow' && <span className="text-accent">Following</span>}
        {preference === 'less' && <span className="text-augustus-400">Lower priority</span>}
      </div>
      <h3 className="font-medium text-augustus-100">{story.title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-augustus-300">{story.development}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" disabled={busy} aria-pressed={preference === 'follow'}
          onClick={() => update.mutate(preference === 'follow' ? 'normal' : 'follow')}
          className={clsx('btn btn-ghost text-xs flex items-center gap-1.5 disabled:opacity-50', preference === 'follow' && 'text-accent')}>
          <Bell className="h-3.5 w-3.5" />{preference === 'follow' ? 'Following story' : 'Follow story'}
        </button>
        <button type="button" disabled={busy} aria-pressed={preference === 'less'}
          onClick={() => update.mutate(preference === 'less' ? 'normal' : 'less')}
          className={clsx('btn btn-ghost text-xs flex items-center gap-1.5 disabled:opacity-50', preference === 'less' && 'text-accent')}>
          <BellOff className="h-3.5 w-3.5" />{preference === 'less' ? 'Restore priority' : 'Less of this'}
        </button>
        {(update.isPending || current.isPending) && <Loader2 aria-label="Saving preference" className="h-4 w-4 animate-spin text-augustus-400" />}
      </div>
      {(update.isError || current.isError) && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          Could not {current.isError ? 'load' : 'save'} your preference.{' '}
          <button type="button" className="underline" onClick={() => current.isError ? current.refetch() : update.reset()}>Try again</button>
        </p>
      )}
      {claims.length > 0 && (
        <details className="mt-4 border-t border-augustus-700/50 pt-3">
          <summary className="cursor-pointer text-sm text-augustus-300">Research and evidence ({claims.length})</summary>
          <p className="mt-2 text-xs text-augustus-400">Source excerpts show where findings came from. Unverified notes are research leads.</p>
          <div className="mt-3 space-y-4">
            {claims.map((claim, index) => (
              <div key={index} className="text-sm">
                <p className="text-augustus-200">{claim.text}</p>
                <p className="mt-1 text-xs text-augustus-400">
                  {(claim.found_by ?? []).join(', ')}{!claim.sources?.length && ' · Unverified'}
                </p>
                {(claim.sources ?? []).filter(source => /^https?:\/\//i.test(source.url)).map((source, sourceIndex) => (
                  <blockquote key={`${source.url}-${sourceIndex}`} className="mt-2 border-l-2 border-accent/40 pl-3">
                    <p className="text-xs leading-relaxed text-augustus-400">“{source.excerpt}”</p>
                    <a href={source.url} target="_blank" rel="noopener noreferrer"
                      className="mt-1 inline-flex items-center gap-1 text-xs text-accent hover:underline break-all">
                      {source.title}<ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                  </blockquote>
                ))}
              </div>
            ))}
          </div>
        </details>
      )}
    </article>
  )
}

export default function StoryDevelopments({ stories }: { stories?: Record<string, StoryChapter> }) {
  const profileId = useStore(s => s.currentProfile?.id)
  const entries = Object.entries(stories ?? {}).sort(([a], [b]) => Number(a) - Number(b))
  if (!profileId || entries.length === 0) return null
  return (
    <section className="card mb-4 sm:mb-6" aria-label="Story developments">
      <h2 className="text-lg font-semibold text-augustus-100">In this briefing</h2>
      <p className="mt-1 mb-4 text-sm text-augustus-400">Follow the stories you want Augustus to keep watching in future briefings.</p>
      <div className="space-y-3">
        {entries.map(([index, story]) => <StoryCard key={`${profileId}-${story.story_id}-${index}`} story={story} profileId={profileId} />)}
      </div>
    </section>
  )
}
