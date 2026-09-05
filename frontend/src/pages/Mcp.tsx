import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Plug,
  BookOpen,
  FileText,
  Key,
  ToggleLeft,
  Activity,
  Plus,
  Copy,
  Check,
  Trash2,
  Ban,
  Loader2,
  AlertCircle,
  ShieldCheck,
  XCircle,
  CheckCircle2,
} from 'lucide-react'
import clsx from 'clsx'
import {
  mcpApi,
  profilesApi,
  McpApiKey,
  McpApiKeyCreated,
  McpToolCatalogItem,
  Profile,
} from '../api/client'

type Tab = 'setup' | 'docs' | 'keys' | 'tools' | 'activity'

const TAB_DEFS: { id: Tab; label: string; icon: typeof BookOpen }[] = [
  { id: 'setup', label: 'Setup', icon: BookOpen },
  { id: 'docs', label: 'Docs', icon: FileText },
  { id: 'keys', label: 'API Keys', icon: Key },
  { id: 'tools', label: 'Tools', icon: ToggleLeft },
  { id: 'activity', label: 'Activity', icon: Activity },
]

export default function Mcp() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = (searchParams.get('tab') as Tab) || 'setup'
  const setActiveTab = (tab: Tab) =>
    setSearchParams(tab === 'setup' ? {} : { tab })

  return (
    <div className="page-container">
      <div className="mb-6 sm:mb-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2 flex items-center gap-3">
              <Plug className="w-6 h-6 text-accent" />
              MCP
            </h1>
            <p className="text-sm sm:text-base text-augustus-400">
              Connect AI agents (Claude Desktop, Claude Code, Cursor) to manage Augustus briefings.
            </p>
          </div>
        </div>

        <div className="flex gap-1 mt-6 border-b border-augustus-800 overflow-x-auto">
          {TAB_DEFS.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={clsx(
                'px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2 whitespace-nowrap',
                activeTab === t.id
                  ? 'bg-augustus-800 text-white border-b-2 border-accent -mb-px'
                  : 'text-augustus-400 hover:text-white hover:bg-augustus-800/50'
              )}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'setup' && <SetupTab />}
      {activeTab === 'docs' && <DocsTab />}
      {activeTab === 'keys' && <KeysTab />}
      {activeTab === 'tools' && <ToolsTab />}
      {activeTab === 'activity' && <ActivityTab />}
    </div>
  )
}

// ============================================================
// Setup
// ============================================================

function SetupTab() {
  const { data: serverInfo } = useQuery({
    queryKey: ['mcp', 'server-info'],
    queryFn: mcpApi.serverInfo,
  })

  const apiUrl =
    serverInfo?.api_url ||
    (typeof window !== 'undefined'
      ? window.location.origin.replace(/\/$/, '')
      : 'http://localhost:8000')

  // Paths are filled in by the backend when it can resolve them (i.e. the MCP
  // client runs on this same machine); otherwise they're placeholders to edit.
  const command = serverInfo?.python_path || 'python'
  const args = [serverInfo?.mcp_script_path || '/path/to/augustus/backend/mcp_server.py']

  const clientConfig = JSON.stringify(
    {
      mcpServers: {
        augustus: {
          command,
          args,
          env: {
            AUGUSTUS_API_URL: apiUrl,
            AUGUSTUS_API_KEY: 'aug_your_key_here',
          },
        },
      },
    },
    null,
    2,
  )

  const claudeCode = `claude mcp add augustus \\
  --env AUGUSTUS_API_URL=${apiUrl} \\
  --env AUGUSTUS_API_KEY=aug_your_key_here \\
  -- "${command}" "${args[0]}"`

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-2">1. Generate an API key</h2>
        <p className="text-sm text-augustus-400">
          Go to the <strong className="text-white">API Keys</strong> tab, create a key,
          and copy it. You will only see the raw key once.
        </p>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-2">2. Configure your client</h2>
        <p className="text-xs text-augustus-500 mb-3">
          The MCP server is the bundled script{' '}
          <code className="text-augustus-300">backend/mcp_server.py</code>; run it with the
          backend's Python. Snippets below point at{' '}
          <code className="text-augustus-300">{apiUrl}</code>
          {serverInfo?.mcp_script_path
            ? ' with the script and interpreter paths filled in.'
            : '. Replace the placeholder path with your checkout location.'}
        </p>

        <ConfigSection
          title="Claude Desktop / Cursor"
          subtitle="Add to claude_desktop_config.json or ~/.cursor/mcp.json"
          code={clientConfig}
        />
        <ConfigSection
          title="Claude Code"
          subtitle="Run in a terminal"
          code={claudeCode}
        />
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-2">3. Verify</h2>
        <p className="text-sm text-augustus-400">
          Restart your client. Ask the agent: <em className="text-white">"List my Augustus briefings."</em>{' '}
          Activity will show under the <strong className="text-white">Activity</strong> tab. The{' '}
          <strong className="text-white">Docs</strong> tab explains what each tool does and the
          workflows agents should follow.
        </p>
      </div>
    </div>
  )
}

// ============================================================
// Docs
// ============================================================

// Groups and parameter hints for the tool reference. Names and descriptions
// come from the live catalog (/api/mcp/tools); anything listed here that the
// backend no longer exposes is simply not rendered.
const TOOL_GROUPS: { title: string; blurb: string; tools: string[] }[] = [
  {
    title: 'Briefings',
    blurb: 'Read, generate, and manage episodes. Generation is asynchronous.',
    tools: [
      'list_briefings',
      'get_briefing',
      'list_generation_queue',
      'generate_briefing',
      'generate_breakout_podcast',
      'cancel_briefing',
      'regenerate_audio',
      'set_briefing_favorite',
      'set_briefing_listened',
      'delete_briefing',
    ],
  },
  {
    title: 'Story memory',
    blurb: 'Steer what future daily briefings emphasise.',
    tools: ['set_story_preference'],
  },
  {
    title: 'Topics',
    blurb: 'What the profile follows. Active topics feed briefings with no explicit topic_ids.',
    tools: ['list_topics', 'create_topic', 'update_topic', 'delete_topic'],
  },
  {
    title: 'Schedules',
    blurb: 'Recurring briefings.',
    tools: [
      'list_scheduled_briefings',
      'create_scheduled_briefing',
      'toggle_scheduled_briefing',
      'trigger_scheduled_briefing',
    ],
  },
  {
    title: 'Casts and profiles',
    blurb: 'Voices and hosts, plus instance-level information.',
    tools: ['list_casts', 'list_profiles'],
  },
]

const TOOL_PARAMS: Record<string, string> = {
  list_briefings: 'limit?, offset?, listened?, favorite?, cast_id?, topic_ids?',
  get_briefing: 'briefing_id, include_transcript? (default true)',
  list_generation_queue: '',
  generate_briefing: 'topic_ids?, cast_id?, max_duration_minutes?',
  generate_breakout_podcast:
    'topic | topic_id | source_briefing_id + chapter_index, focus?, max_duration_minutes? (3-30), cast_id?',
  cancel_briefing: 'briefing_id',
  regenerate_audio: 'briefing_id, cast_id',
  set_briefing_favorite: 'briefing_id, favorite',
  set_briefing_listened: 'briefing_id, listened',
  delete_briefing: 'briefing_id',
  set_story_preference: 'story_id, preference ("follow" | "less" | "normal")',
  list_topics: '',
  create_topic: 'name, description?, color?, use_newsapi?, enable_site_generation?',
  update_topic: 'topic_id, name?, description?, color?, is_active?, use_newsapi?, enable_site_generation?',
  delete_topic: 'topic_id',
  list_scheduled_briefings: '',
  create_scheduled_briefing:
    'name, schedule_time ("HH:MM"), schedule_days (0=Mon..6=Sun), topic_ids?, cast_id?, max_duration_minutes?, is_active?',
  toggle_scheduled_briefing: 'schedule_id',
  trigger_scheduled_briefing: 'schedule_id',
  list_casts: '',
  list_profiles: '',
}

const DESTRUCTIVE_TOOLS = new Set(['delete_briefing', 'delete_topic'])
const ASYNC_TOOLS = new Set([
  'generate_briefing',
  'generate_breakout_podcast',
  'regenerate_audio',
  'trigger_scheduled_briefing',
])

function DocsTab() {
  const { data: tools } = useQuery({ queryKey: ['mcp', 'tools'], queryFn: mcpApi.listTools })
  const byName = useMemo(
    () => new Map((tools || []).map((t) => [t.name, t] as const)),
    [tools],
  )

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-2">How it works</h2>
        <ul className="text-sm text-augustus-400 space-y-2 list-disc pl-5">
          <li>
            The MCP server is a thin proxy over the Augustus REST API. Every tool call runs
            with the <strong className="text-white">API key's bound profile</strong>; agents
            never pass a profile or user id, and a key cannot switch profiles.
          </li>
          <li>
            Each key can be restricted to a subset of tools under{' '}
            <strong className="text-white">Tools</strong>. Disabled tools are hidden from the
            agent and denied if called anyway.
          </li>
          <li>
            Every call (success, error, or denied) is written to the{' '}
            <strong className="text-white">Activity</strong> audit log with its arguments.
          </li>
          <li>
            The server also publishes an <code className="text-augustus-300">augustus://guide</code>{' '}
            resource: a longer agent-facing version of this page that clients can read on demand.
          </li>
          <li>
            API-key identity is not network security. Keep the backend behind your own access
            controls; revoke a key from <strong className="text-white">API Keys</strong> if it leaks.
          </li>
        </ul>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-2">Generation is asynchronous</h2>
        <p className="text-sm text-augustus-400 mb-3">
          <code className="text-augustus-300">generate_briefing</code>,{' '}
          <code className="text-augustus-300">generate_breakout_podcast</code>,{' '}
          <code className="text-augustus-300">regenerate_audio</code>, and{' '}
          <code className="text-augustus-300">trigger_scheduled_briefing</code> return
          immediately with status <code className="text-augustus-300">queued</code>. Audio and
          transcript usually take 2 to 8 minutes. Agents poll{' '}
          <code className="text-augustus-300">get_briefing</code> until the status is{' '}
          <code className="text-augustus-300">completed</code>,{' '}
          <code className="text-augustus-300">failed</code>, or{' '}
          <code className="text-augustus-300">cancelled</code>. Jobs run one at a time, oldest
          first, survive restarts, and can be listed with{' '}
          <code className="text-augustus-300">list_generation_queue</code>.
        </p>
        <p className="text-sm text-augustus-400">
          Every briefing the tools return carries two ready-made links:{' '}
          <code className="text-augustus-300">detail_url</code> (the in-app page, available
          right away) and <code className="text-augustus-300">listen_url</code> (the audio file,
          present once completed). Agents hand these to you verbatim.
        </p>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-3">Common workflows</h2>
        <div className="space-y-4">
          <Workflow
            title="Briefing about a new subject"
            steps={[
              'create_topic(name) → note the returned id',
              'generate_briefing(topic_ids=[id]) → note the briefing id',
              'poll get_briefing(briefing_id, include_transcript=false) until completed',
            ]}
          />
          <Workflow
            title="Deep dive (breakout podcast)"
            steps={[
              'Pick exactly one subject: topic="…", topic_id="…", or source_briefing_id + chapter_index',
              'Optionally add focus, max_duration_minutes (3-30), cast_id',
              'generate_breakout_podcast(...) then poll get_briefing as above',
            ]}
          />
          <Workflow
            title="Steer future coverage (story memory)"
            steps={[
              'get_briefing(briefing_id) → read the stories list (story_id per chapter)',
              'set_story_preference(story_id, "follow") to hear more, "less" to hear less, "normal" to reset',
            ]}
          />
          <Workflow
            title="Manage what the profile follows"
            steps={[
              'list_topics() shows every topic and whether it is active',
              'update_topic(topic_id, is_active=false) pauses a topic; delete_topic removes it permanently',
              'create_scheduled_briefing(name, schedule_time, schedule_days) sets up a recurring episode',
            ]}
          />
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-1">Tool reference</h2>
        <p className="text-xs text-augustus-500 mb-4">
          {tools
            ? `${tools.length} tools exposed by this server. Restart a connected client after upgrading Augustus so it refreshes the list.`
            : 'Loading catalog…'}
        </p>
        <div className="space-y-6">
          {TOOL_GROUPS.map((group) => {
            const present = group.tools.filter((name) => byName.has(name))
            if (present.length === 0) return null
            return (
              <div key={group.title}>
                <h3 className="text-sm font-semibold text-white">{group.title}</h3>
                <p className="text-xs text-augustus-500 mb-2">{group.blurb}</p>
                <div className="divide-y divide-augustus-800/60 border border-augustus-800 rounded-lg overflow-hidden">
                  {present.map((name) => {
                    const t = byName.get(name) as McpToolCatalogItem
                    return (
                      <div key={name} className="px-3 py-2 bg-augustus-950/40">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm text-white font-mono">{t.name}</span>
                          <Badge tone={t.category === 'write' ? 'amber' : 'muted'}>{t.category}</Badge>
                          {ASYNC_TOOLS.has(name) && <Badge tone="blue">async</Badge>}
                          {DESTRUCTIVE_TOOLS.has(name) && <Badge tone="red">permanent</Badge>}
                        </div>
                        <p className="text-xs text-augustus-400 mt-0.5">{t.description}</p>
                        {TOOL_PARAMS[name] ? (
                          <p className="text-[11px] text-augustus-500 font-mono mt-1 break-words">
                            {TOOL_PARAMS[name]}
                          </p>
                        ) : (
                          <p className="text-[11px] text-augustus-600 mt-1">no arguments</p>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Workflow({ title, steps }: { title: string; steps: string[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
      <ol className="text-xs text-augustus-400 space-y-1 list-decimal pl-5 font-mono">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </div>
  )
}

function Badge({ tone, children }: { tone: 'amber' | 'muted' | 'blue' | 'red'; children: string }) {
  return (
    <span
      className={clsx(
        'text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wide',
        tone === 'amber' && 'bg-amber-500/20 text-amber-300',
        tone === 'muted' && 'bg-augustus-800 text-augustus-400',
        tone === 'blue' && 'bg-sky-500/20 text-sky-300',
        tone === 'red' && 'bg-red-500/20 text-red-300',
      )}
    >
      {children}
    </span>
  )
}

function ConfigSection({
  title,
  subtitle,
  code,
}: {
  title: string
  subtitle: string
  code: string
}) {
  return (
    <div className="mt-4 first:mt-0">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <span className="text-xs text-augustus-500">{subtitle}</span>
      </div>
      <CodeBlock code={code} />
    </div>
  )
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="relative group">
      <pre className="bg-augustus-950/60 border border-augustus-800 rounded-lg p-3 text-xs text-augustus-200 overflow-x-auto">
        <code>{code}</code>
      </pre>
      <button
        onClick={copy}
        className="absolute top-2 right-2 p-1.5 rounded bg-augustus-800/80 hover:bg-augustus-700 text-augustus-300 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Copy"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    </div>
  )
}

// ============================================================
// API Keys
// ============================================================

function KeysTab() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [newKey, setNewKey] = useState<McpApiKeyCreated | null>(null)

  const { data: keys, isLoading } = useQuery({
    queryKey: ['mcp', 'keys'],
    queryFn: mcpApi.listKeys,
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => mcpApi.revokeKey(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mcp', 'keys'] }),
  })
  const deleteMutation = useMutation({
    mutationFn: (id: string) => mcpApi.deleteKey(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mcp', 'keys'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-augustus-400">
          Each key is bound to a profile. The agent acts as that profile.
        </p>
        <button
          onClick={() => setCreating(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Key
        </button>
      </div>

      {newKey && <NewKeyBanner created={newKey} onDismiss={() => setNewKey(null)} />}

      {isLoading ? (
        <div className="card flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : !keys || keys.length === 0 ? (
        <div className="card text-center py-12">
          <Key className="w-10 h-10 text-augustus-500 mx-auto mb-3" />
          <p className="text-augustus-400">No API keys yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((k) => (
            <KeyRow
              key={k.id}
              apiKey={k}
              onRevoke={() => revokeMutation.mutate(k.id)}
              onDelete={() => {
                if (confirm(`Delete API key "${k.name}"? This cannot be undone.`)) {
                  deleteMutation.mutate(k.id)
                }
              }}
            />
          ))}
        </div>
      )}

      {creating && (
        <CreateKeyModal
          onClose={() => setCreating(false)}
          onCreated={(created) => {
            setNewKey(created)
            setCreating(false)
            queryClient.invalidateQueries({ queryKey: ['mcp', 'keys'] })
          }}
        />
      )}
    </div>
  )
}

function NewKeyBanner({ created, onDismiss }: { created: McpApiKeyCreated; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(created.key)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="card border-accent/40 bg-accent/5">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-accent" />
          <h3 className="text-white font-semibold">Save this key now</h3>
        </div>
        <button onClick={onDismiss} className="text-augustus-400 hover:text-white">
          <XCircle className="w-5 h-5" />
        </button>
      </div>
      <p className="text-xs text-augustus-400 mb-3">
        This is the only time the full key will be shown. Store it somewhere safe.
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 bg-augustus-950 border border-augustus-800 rounded px-3 py-2 text-xs text-white font-mono break-all">
          {created.key}
        </code>
        <button onClick={copy} className="btn btn-secondary flex items-center gap-1.5 flex-shrink-0">
          {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

function KeyRow({
  apiKey,
  onRevoke,
  onDelete,
}: {
  apiKey: McpApiKey
  onRevoke: () => void
  onDelete: () => void
}) {
  const revoked = !!apiKey.revoked_at
  return (
    <div className={clsx('card', revoked && 'opacity-60')}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-white font-semibold">{apiKey.name}</h3>
            {revoked && (
              <span className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-300">
                revoked
              </span>
            )}
          </div>
          <p className="text-xs text-augustus-500 font-mono">
            {apiKey.key_prefix}…  ·  profile: {apiKey.profile_name || apiKey.profile_id}
          </p>
          <p className="text-xs text-augustus-500 mt-1">
            {apiKey.last_used_at
              ? `Last used ${new Date(apiKey.last_used_at).toLocaleString()}`
              : 'Never used'}
            {apiKey.last_client && ` · ${apiKey.last_client}`}
          </p>
          {apiKey.enabled_tools && (
            <p className="text-xs text-augustus-500 mt-1">
              Limited to {apiKey.enabled_tools.length} tool{apiKey.enabled_tools.length === 1 ? '' : 's'}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!revoked && (
            <button onClick={onRevoke} className="btn btn-secondary flex items-center gap-1.5">
              <Ban className="w-4 h-4" />
              Revoke
            </button>
          )}
          <button
            onClick={onDelete}
            className="btn btn-ghost text-red-400 hover:text-red-300 flex items-center gap-1.5"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

function CreateKeyModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (created: McpApiKeyCreated) => void
}) {
  const [name, setName] = useState('')
  const [profileId, setProfileId] = useState('')
  const [restrictTools, setRestrictTools] = useState(false)
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())

  const { data: profiles } = useQuery({
    queryKey: ['profiles'],
    queryFn: () => profilesApi.list(),
  })
  const { data: tools } = useQuery({
    queryKey: ['mcp', 'tools'],
    queryFn: mcpApi.listTools,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      mcpApi.createKey({
        name,
        profile_id: profileId,
        enabled_tools: restrictTools ? Array.from(selectedTools) : null,
      }),
    onSuccess: onCreated,
  })

  const ready =
    name.trim().length > 0 && profileId && (!restrictTools || selectedTools.size > 0)

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-augustus-900 border border-augustus-700 rounded-xl max-w-lg w-full max-h-[90vh] flex flex-col">
        <div className="px-5 py-4 border-b border-augustus-800 flex items-center justify-between">
          <h2 className="text-white font-semibold">New API key</h2>
          <button onClick={onClose} className="text-augustus-400 hover:text-white">
            <XCircle className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-4 overflow-auto">
          <div>
            <label className="block text-sm text-augustus-300 mb-1">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My laptop · Claude Desktop"
              className="w-full bg-augustus-950 border border-augustus-700 rounded-lg px-3 py-2 text-white placeholder-augustus-600 focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm text-augustus-300 mb-1">Profile</label>
            <select
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              className="w-full bg-augustus-950 border border-augustus-700 rounded-lg px-3 py-2 text-white focus:border-accent focus:outline-none"
            >
              <option value="">Select a profile…</option>
              {profiles?.profiles.map((p: Profile) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <p className="text-xs text-augustus-500 mt-1">
              The agent will act as this profile.
            </p>
          </div>
          <div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={restrictTools}
                onChange={(e) => setRestrictTools(e.target.checked)}
                className="accent-accent"
              />
              <span className="text-sm text-augustus-300">Restrict tools</span>
            </label>
            {restrictTools && tools && (
              <div className="mt-2 space-y-1 max-h-64 overflow-auto border border-augustus-800 rounded-lg p-2">
                {tools.map((t) => (
                  <ToolCheckbox
                    key={t.name}
                    tool={t}
                    checked={selectedTools.has(t.name)}
                    onToggle={() => {
                      const next = new Set(selectedTools)
                      if (next.has(t.name)) next.delete(t.name)
                      else next.add(t.name)
                      setSelectedTools(next)
                    }}
                  />
                ))}
              </div>
            )}
          </div>
          {createMutation.isError && (
            <div className="text-sm text-red-400 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {(createMutation.error as Error).message || 'Failed to create key'}
            </div>
          )}
        </div>
        <div className="px-5 py-4 border-t border-augustus-800 flex justify-end gap-2">
          <button onClick={onClose} className="btn btn-ghost">
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!ready || createMutation.isPending}
            className="btn btn-primary flex items-center gap-2"
          >
            {createMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Create key
          </button>
        </div>
      </div>
    </div>
  )
}

function ToolCheckbox({
  tool,
  checked,
  onToggle,
}: {
  tool: McpToolCatalogItem
  checked: boolean
  onToggle: () => void
}) {
  return (
    <label className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-augustus-800/50 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={onToggle} className="mt-0.5 accent-accent" />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-white font-mono">{tool.name}</span>
          <span
            className={clsx(
              'text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wide',
              tool.category === 'write'
                ? 'bg-amber-500/20 text-amber-300'
                : 'bg-augustus-800 text-augustus-400',
            )}
          >
            {tool.category}
          </span>
        </div>
        <p className="text-xs text-augustus-500">{tool.description}</p>
      </div>
    </label>
  )
}

// ============================================================
// Tools (per-key toggles)
// ============================================================

function ToolsTab() {
  const queryClient = useQueryClient()
  const { data: keys } = useQuery({ queryKey: ['mcp', 'keys'], queryFn: mcpApi.listKeys })
  const { data: tools } = useQuery({ queryKey: ['mcp', 'tools'], queryFn: mcpApi.listTools })
  const [selectedKeyId, setSelectedKeyId] = useState<string>('')

  const activeKeys = useMemo(() => (keys || []).filter((k) => !k.revoked_at), [keys])
  const selected = activeKeys.find((k) => k.id === selectedKeyId) || activeKeys[0]

  const updateMutation = useMutation({
    mutationFn: (payload: { id: string; enabled_tools: string[] | null }) =>
      mcpApi.updateKey(payload.id, { enabled_tools: payload.enabled_tools }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mcp', 'keys'] }),
  })

  if (!keys) {
    return (
      <div className="card flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-accent" />
      </div>
    )
  }

  if (activeKeys.length === 0) {
    return (
      <div className="card text-center py-12">
        <Key className="w-10 h-10 text-augustus-500 mx-auto mb-3" />
        <p className="text-augustus-400">Create an API key first to manage its tools.</p>
      </div>
    )
  }

  if (!selected || !tools) return null

  const enabledSet = new Set(selected.enabled_tools ?? tools.map((t) => t.name))
  const allEnabled = selected.enabled_tools === null || selected.enabled_tools === undefined

  const toggle = (name: string) => {
    const current = new Set(selected.enabled_tools ?? tools.map((t) => t.name))
    if (current.has(name)) current.delete(name)
    else current.add(name)
    updateMutation.mutate({ id: selected.id, enabled_tools: Array.from(current) })
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <label className="block text-sm text-augustus-300 mb-1">API key</label>
        <select
          value={selected.id}
          onChange={(e) => setSelectedKeyId(e.target.value)}
          className="w-full bg-augustus-950 border border-augustus-700 rounded-lg px-3 py-2 text-white focus:border-accent focus:outline-none"
        >
          {activeKeys.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name} ({k.profile_name})
            </option>
          ))}
        </select>
        <div className="flex items-center justify-between mt-3">
          <p className="text-xs text-augustus-500">
            {allEnabled ? 'All tools enabled.' : `${selected.enabled_tools?.length} of ${tools.length} tools enabled.`}
          </p>
          <button
            onClick={() =>
              updateMutation.mutate({
                id: selected.id,
                enabled_tools: allEnabled ? [] : null,
              })
            }
            className="btn btn-ghost text-xs"
          >
            {allEnabled ? 'Restrict tools' : 'Enable all'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="space-y-1">
          {tools.map((t) => {
            const on = enabledSet.has(t.name)
            return (
              <button
                key={t.name}
                onClick={() => toggle(t.name)}
                className="w-full flex items-start justify-between gap-3 px-2 py-2 rounded hover:bg-augustus-800/50 transition-colors text-left"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white font-mono">{t.name}</span>
                    <span
                      className={clsx(
                        'text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wide',
                        t.category === 'write'
                          ? 'bg-amber-500/20 text-amber-300'
                          : 'bg-augustus-800 text-augustus-400',
                      )}
                    >
                      {t.category}
                    </span>
                  </div>
                  <p className="text-xs text-augustus-500">{t.description}</p>
                </div>
                <div
                  className={clsx(
                    'flex-shrink-0 w-10 h-6 rounded-full p-0.5 transition-colors',
                    on ? 'bg-accent' : 'bg-augustus-700',
                  )}
                >
                  <div
                    className={clsx(
                      'w-5 h-5 rounded-full bg-white transition-transform',
                      on && 'translate-x-4',
                    )}
                  />
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ============================================================
// Activity
// ============================================================

function ActivityTab() {
  const { data: clients } = useQuery({
    queryKey: ['mcp', 'clients'],
    queryFn: mcpApi.listClients,
    refetchInterval: 15000,
  })
  const { data: audit, isLoading } = useQuery({
    queryKey: ['mcp', 'audit'],
    queryFn: () => mcpApi.listAudit(200),
    refetchInterval: 10000,
  })

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="text-white font-semibold mb-3">Connected clients (last 24h)</h2>
        {!clients || clients.length === 0 ? (
          <p className="text-sm text-augustus-500">No active clients.</p>
        ) : (
          <div className="space-y-2">
            {clients.map((c) => (
              <div
                key={`${c.api_key_id}-${c.client}`}
                className="flex items-center justify-between gap-3 p-2 rounded bg-augustus-950/50"
              >
                <div className="min-w-0">
                  <p className="text-sm text-white truncate">{c.api_key_name}</p>
                  <p className="text-xs text-augustus-500 truncate">{c.client || 'unknown client'}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-xs text-augustus-300">{c.request_count_24h} reqs</p>
                  <p className="text-[10px] text-augustus-500">
                    {new Date(c.last_seen).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="text-white font-semibold mb-3">Audit log</h2>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-accent" />
          </div>
        ) : !audit || audit.length === 0 ? (
          <p className="text-sm text-augustus-500">No tool calls yet.</p>
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase text-augustus-500">
                  <th className="text-left font-medium px-5 py-2">When</th>
                  <th className="text-left font-medium px-2 py-2">Key</th>
                  <th className="text-left font-medium px-2 py-2">Tool</th>
                  <th className="text-left font-medium px-2 py-2">Status</th>
                  <th className="text-right font-medium px-5 py-2">ms</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((e) => (
                  <tr key={e.id} className="border-t border-augustus-800/50">
                    <td className="px-5 py-2 text-augustus-400 text-xs whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td className="px-2 py-2 text-augustus-300 text-xs">
                      {e.api_key_name || '—'}
                    </td>
                    <td className="px-2 py-2 text-white font-mono text-xs">{e.tool_name}</td>
                    <td className="px-2 py-2">
                      <StatusPill status={e.status} error={e.error} />
                    </td>
                    <td className="px-5 py-2 text-right text-augustus-500 text-xs">
                      {e.duration_ms ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function StatusPill({ status, error }: { status: string; error?: string | null }) {
  const styles =
    status === 'success'
      ? 'bg-green-500/15 text-green-300'
      : status === 'denied'
        ? 'bg-amber-500/15 text-amber-300'
        : 'bg-red-500/15 text-red-300'
  const Icon = status === 'success' ? CheckCircle2 : status === 'denied' ? Ban : XCircle
  return (
    <span
      className={clsx('inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded', styles)}
      title={error || undefined}
    >
      <Icon className="w-3 h-3" />
      {status}
    </span>
  )
}
