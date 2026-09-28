import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Settings as SettingsIcon,
  Cpu,
  Rss,
  Loader2,
  CheckCircle,
  AlertCircle,
  Info,
  Globe,
  Mail,
  Sparkles,
  MoreVertical,
  RotateCw,
  Users,
  Plug
} from 'lucide-react'
import clsx from 'clsx'
import { castsApi, settingsApi } from '../api/client'
import { providerLabel } from './castProviders'
import CodexSettings from '../components/CodexSettings'
import ProfileManagement from '../components/ProfileManagement'
import ContentSettings from '../components/settings/ContentSettings'
import OpenRouterSettings from '../components/settings/OpenRouterSettings'
import TextGenerationProvider, { type LlmProvider } from '../components/settings/TextGenerationProvider'
import TtsSettings from '../components/settings/TtsSettings'
import {
  SecretInput,
  SettingsCheckbox,
  SettingsGroup,
  SettingsJumpBar,
  SettingsLinkCard,
} from '../components/settings/SettingsControls'
import { SETTINGS_GROUPS, durationToSlider, sliderToDuration } from '../components/settings/settingsLogic'
import { useProfileNavigate } from '../utils/profileSlug'

type SettingsTab = 'general' | 'profiles'

const [AI_VOICE_GROUP, CONTENT_GROUP, APP_GROUP] = SETTINGS_GROUPS

export default function Settings() {
  const navigate = useProfileNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()

  // Tab state from URL
  const activeTab = (searchParams.get('tab') as SettingsTab) || 'general'
  const setActiveTab = (tab: SettingsTab) => {
    setSearchParams(tab === 'general' ? {} : { tab })
  }

  // Form state
  const [llmProvider, setLlmProvider] = useState<LlmProvider>('openrouter')
  const [codexModel, setCodexModel] = useState('')
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [openrouterModel, setOpenrouterModel] = useState('')
  const [openrouterWriterModel, setOpenrouterWriterModel] = useState('')
  const [ttsProvider, setTtsProvider] = useState('piper')
  const [piperUrl, setPiperUrl] = useState('')
  const [elevenlabsKey, setElevenlabsKey] = useState('')
  const [elevenlabsModel, setElevenlabsModel] = useState('eleven_turbo_v2_5')
  const [geminiKey, setGeminiKey] = useState('')
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash-preview-tts')
  const [enableNonSpeechSounds, setEnableNonSpeechSounds] = useState(false)
  // Duration slider values (1=Short/3min, 2=Medium/7min, 3=Long/25min)
  const [briefingDurationSlider, setBriefingDurationSlider] = useState(2)
  const [conversationComplexity, setConversationComplexity] = useState(3)
  const [timezone, setTimezone] = useState('UTC')
  const [newsApiKey, setNewsApiKey] = useState('')
  const [resendApiKey, setResendApiKey] = useState('')
  const [resendFromEmail, setResendFromEmail] = useState('')
  const [autoPlayNext, setAutoPlayNext] = useState(false)

  // UI state
  const [saved, setSaved] = useState(false)
  const [providerSaving, setProviderSaving] = useState(false)
  const [providerSaveError, setProviderSaveError] = useState<string | null>(null)
  const [showMobileMenu, setShowMobileMenu] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const providerHydratedRef = useRef(false)
  const providerSaveLockRef = useRef(false)

  // Fetch current settings
  const { data: settings, isLoading, error } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.get(),
  })

  // Fetch available models
  const { data: models, isLoading: modelsLoading } = useQuery({
    queryKey: ['models'],
    queryFn: () => settingsApi.getModels(),
  })

  // Fetch available timezones
  const { data: timezones } = useQuery({
    queryKey: ['timezones'],
    queryFn: () => settingsApi.getTimezones(),
  })

  const { data: castSummary } = useQuery({ queryKey: ['casts', 'summary'], queryFn: () => castsApi.summary() })
  const { data: castList } = useQuery({ queryKey: ['casts'], queryFn: () => castsApi.list() })

  // Update settings mutation
  const updateMutation = useMutation({
    mutationFn: settingsApi.update,
    onSuccess: (_data, variables) => {
      queryClient.setQueryData(['settings'], (old: any) => {
        if (!old) return old
        const updated = { ...old, ...variables }
        if ('openrouter_api_key' in variables) updated.openrouter_configured = true
        if ('elevenlabs_api_key' in variables) updated.elevenlabs_configured = true
        if ('gemini_api_key' in variables) updated.gemini_configured = true
        if ('resend_api_key' in variables) updated.resend_configured = true
        return updated
      })
      // Casts are per provider: every cast list and picker must follow a provider switch.
      if ('tts_provider' in variables) {
        queryClient.invalidateQueries({ queryKey: ['casts'] })
        queryClient.invalidateQueries({ queryKey: ['cast-voices'] })
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  const restartMutation = useMutation({
    mutationFn: () => settingsApi.restartServer(),
    onSuccess: () => {
      setShowMobileMenu(false)
      // Show a message that the server is restarting
      alert('Server restart initiated. The page will refresh in a few seconds.')
      // Reload the page after a short delay
      setTimeout(() => {
        window.location.reload()
      }, 2000)
    },
    onError: (error: any) => {
      alert(`Failed to restart server: ${error?.response?.data?.detail || error.message}`)
    },
  })

  const saveProviderSetting = useCallback(async (
    updates: { llm_provider?: LlmProvider; codex_model?: string },
  ): Promise<boolean> => {
    if (providerSaveLockRef.current) return false
    providerSaveLockRef.current = true
    setProviderSaving(true)
    setProviderSaveError(null)

    try {
      await settingsApi.update(updates)
      queryClient.setQueryData(['settings'], (old: any) => old ? { ...old, ...updates } : old)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      return true
    } catch (error: any) {
      setProviderSaveError(error?.response?.data?.detail || error?.message || 'Could not save the text generation provider.')
      return false
    } finally {
      providerSaveLockRef.current = false
      setProviderSaving(false)
    }
  }, [queryClient])

  // Switching provider unmounts the OpenRouter card, which also closes its model pickers.
  const handleProviderChange = useCallback(async (nextProvider: LlmProvider) => {
    if (nextProvider === llmProvider || providerSaveLockRef.current) return
    const previousProvider = llmProvider
    setLlmProvider(nextProvider)
    const savedProvider = await saveProviderSetting({ llm_provider: nextProvider })
    if (!savedProvider) setLlmProvider(previousProvider)
  }, [llmProvider, saveProviderSetting])

  const handleCodexModelChange = useCallback(async (nextModel: string) => {
    if (nextModel === codexModel || providerSaveLockRef.current) return
    const previousModel = codexModel
    setCodexModel(nextModel)
    const savedModel = await saveProviderSetting({ codex_model: nextModel })
    if (!savedModel) setCodexModel(previousModel)
  }, [codexModel, saveProviderSetting])

  // Initialize form with current settings
  useEffect(() => {
    if (settings) {
      // Provider state is hydrated once so cache refetches and overlapping saves cannot
      // replace a newer local selection with an older response.
      if (!providerHydratedRef.current) {
        setLlmProvider(settings.llm_provider || 'openrouter')
        setCodexModel(settings.codex_model || '')
        providerHydratedRef.current = true
      }
      setOpenrouterModel(settings.openrouter_model)
      setOpenrouterWriterModel(settings.openrouter_writer_model || '')
      setTtsProvider(settings.tts_provider)
      setPiperUrl(settings.piper_url || '')
      setElevenlabsModel(settings.elevenlabs_model || 'eleven_turbo_v2_5')
      setGeminiModel(settings.gemini_model || 'gemini-2.5-flash-preview-tts')
      setEnableNonSpeechSounds(settings.enable_non_speech_sounds || false)
      setBriefingDurationSlider(durationToSlider(settings.briefing_duration_minutes))
      setConversationComplexity(settings.conversation_complexity || 3)
      setTimezone(settings.timezone || 'UTC')
      setAutoPlayNext(settings.auto_play_next || false)
      // Show masked keys if user hasn't typed anything yet
      if (!openrouterKey && settings.openrouter_api_key) {
        setOpenrouterKey(settings.openrouter_api_key)
      }
      if (!elevenlabsKey && settings.elevenlabs_api_key) {
        setElevenlabsKey(settings.elevenlabs_api_key)
      }
      if (!geminiKey && settings.gemini_api_key) {
        setGeminiKey(settings.gemini_api_key)
      }
      if (!newsApiKey && settings.news_api_key) {
        setNewsApiKey(settings.news_api_key)
      }
      if (!resendApiKey && settings.resend_api_key) {
        setResendApiKey(settings.resend_api_key)
      }
      if (settings.resend_from_email !== undefined) {
        setResendFromEmail(settings.resend_from_email || '')
      }
    }
  }, [settings])

  const handleSave = useCallback(() => {
    if (!settings) return

    const updates: Record<string, string | number | boolean> = {}

    // Helper to check if a key is a new value (not the masked version)
    const isNewKey = (value: string, maskedValue?: string) => {
      if (!value) return false
      if (value.includes('...')) return false
      if (value === maskedValue) return false
      return true
    }

    // Only send API keys if they're new (not masked values)
    if (isNewKey(openrouterKey, settings.openrouter_api_key)) updates.openrouter_api_key = openrouterKey
    if (isNewKey(elevenlabsKey, settings.elevenlabs_api_key)) updates.elevenlabs_api_key = elevenlabsKey
    if (isNewKey(geminiKey, settings.gemini_api_key)) updates.gemini_api_key = geminiKey
    if (isNewKey(newsApiKey, settings.news_api_key)) updates.news_api_key = newsApiKey
    if (isNewKey(resendApiKey, settings.resend_api_key)) updates.resend_api_key = resendApiKey

    // Non-key settings - normalize null/undefined/empty for comparison
    if ((resendFromEmail || '') !== (settings.resend_from_email || '')) updates.resend_from_email = resendFromEmail || ''
    if (openrouterModel !== settings.openrouter_model) updates.openrouter_model = openrouterModel
    if ((openrouterWriterModel || '') !== (settings.openrouter_writer_model || '')) updates.openrouter_writer_model = openrouterWriterModel || ''
    if (ttsProvider !== settings.tts_provider) updates.tts_provider = ttsProvider
    if ((piperUrl || '') !== (settings.piper_url || '')) updates.piper_url = piperUrl
    if ((elevenlabsModel || '') !== (settings.elevenlabs_model || '')) updates.elevenlabs_model = elevenlabsModel
    if ((geminiModel || '') !== (settings.gemini_model || '')) updates.gemini_model = geminiModel
    if (enableNonSpeechSounds !== (settings.enable_non_speech_sounds || false)) updates.enable_non_speech_sounds = enableNonSpeechSounds
    const briefingDuration = sliderToDuration(briefingDurationSlider)
    if (briefingDuration !== settings.briefing_duration_minutes) updates.briefing_duration_minutes = briefingDuration
    if (conversationComplexity !== (settings.conversation_complexity || 3)) updates.conversation_complexity = conversationComplexity
    if ((timezone || 'UTC') !== (settings.timezone || 'UTC')) updates.timezone = timezone
    if (autoPlayNext !== (settings.auto_play_next || false)) updates.auto_play_next = autoPlayNext

    if (Object.keys(updates).length > 0) {
      updateMutation.mutate(updates)
    }
  }, [settings, openrouterKey, openrouterModel, openrouterWriterModel, ttsProvider, piperUrl, elevenlabsKey, elevenlabsModel, geminiKey, geminiModel, enableNonSpeechSounds, briefingDurationSlider, conversationComplexity, timezone, newsApiKey, resendApiKey, resendFromEmail, autoPlayNext, updateMutation])

  // Auto-save: debounce all form value changes
  useEffect(() => {
    if (!settings) return

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      handleSave()
    }, 800)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [handleSave])

  const restartOnboarding = async () => {
    // Clear onboarding flags to restart
    try {
      await settingsApi.update({
        onboarding_completed: false,
        onboarding_skipped: false,
      })
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    } catch (error) {
      console.error('Failed to reset onboarding state:', error)
    }
    navigate('/onboarding')
  }

  if (isLoading) {
    return (
      <div className="page-container flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-container">
        <div className="card text-center py-10 sm:py-12">
          <AlertCircle className="w-10 sm:w-12 h-10 sm:h-12 text-red-500 mx-auto mb-3 sm:mb-4" />
          <p className="text-sm sm:text-base text-augustus-400">Failed to load settings. Is the backend running?</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
              Settings
            </h1>
            <p className="text-sm sm:text-base text-augustus-400 flex items-center gap-2">
              <span>
                {activeTab === 'general'
                  ? 'Configure API keys and integrations for Augustus'
                  : 'Manage user profiles'
                }
              </span>
              {updateMutation.isPending && (
                <span className="inline-flex items-center gap-1 text-xs text-augustus-500">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Saving...
                </span>
              )}
              {saved && !updateMutation.isPending && (
                <span className="inline-flex items-center gap-1 text-xs text-green-400">
                  <CheckCircle className="w-3 h-3" />
                  Saved
                </span>
              )}
            </p>
          </div>

          {/* Desktop: Reset Server Button */}
          <div className="hidden sm:block">
            <button
              onClick={() => {
                if (confirm('Are you sure you want to restart the server? This will reload the configuration without deleting any data.')) {
                  restartMutation.mutate()
                }
              }}
              disabled={restartMutation.isPending}
              className="btn btn-secondary flex items-center gap-2"
            >
              {restartMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Restarting...
                </>
              ) : (
                <>
                  <RotateCw className="w-4 h-4" />
                  Reset Server
                </>
              )}
            </button>
          </div>

          {/* Mobile: Three Dots Menu */}
          <div className="sm:hidden relative">
            <button
              onClick={() => setShowMobileMenu(!showMobileMenu)}
              className="p-2 text-augustus-400 hover:text-white transition-colors"
            >
              <MoreVertical className="w-5 h-5" />
            </button>

            {/* Mobile Menu Dropdown */}
            {showMobileMenu && (
              <>
                <div
                  className="fixed inset-0 z-[100]"
                  onClick={() => setShowMobileMenu(false)}
                />
                <div className="absolute right-0 top-full mt-2 w-56 bg-augustus-900 border border-augustus-700 rounded-lg shadow-xl z-[101] overflow-hidden">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        setShowMobileMenu(false)
                        if (confirm('Are you sure you want to restart the server? This will reload the configuration without deleting any data.')) {
                          restartMutation.mutate()
                        }
                      }}
                      disabled={restartMutation.isPending}
                      className="w-full px-4 py-3 text-left hover:bg-augustus-800 active:bg-augustus-700 transition-colors flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {restartMutation.isPending ? (
                        <>
                          <Loader2 className="w-5 h-5 text-augustus-400 animate-spin" />
                          <div>
                            <span className="text-white font-medium block text-sm">
                              Restarting...
                            </span>
                          </div>
                        </>
                      ) : (
                        <>
                          <RotateCw className="w-5 h-5 text-augustus-400" />
                          <div>
                            <span className="text-white font-medium block text-sm">
                              Reset Server
                            </span>
                            <span className="text-augustus-500 text-xs">
                              Soft restart (no data loss)
                            </span>
                          </div>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-6 border-b border-augustus-800">
          <button
            onClick={() => setActiveTab('general')}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2',
              activeTab === 'general'
                ? 'bg-augustus-800 text-white border-b-2 border-accent -mb-px'
                : 'text-augustus-400 hover:text-white hover:bg-augustus-800/50'
            )}
          >
            <SettingsIcon className="w-4 h-4" />
            General
          </button>
          <button
            onClick={() => setActiveTab('profiles')}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2',
              activeTab === 'profiles'
                ? 'bg-augustus-800 text-white border-b-2 border-accent -mb-px'
                : 'text-augustus-400 hover:text-white hover:bg-augustus-800/50'
            )}
          >
            <Users className="w-4 h-4" />
            Profiles
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'profiles' ? (
        <ProfileManagement />
      ) : (
        <>
          <SettingsJumpBar />

          {/* AI & voice */}
          <SettingsGroup
            id={AI_VOICE_GROUP.id}
            title={AI_VOICE_GROUP.label}
            description="The models that write your briefings and the voices that read them."
          >
            <TextGenerationProvider
              provider={llmProvider}
              onChange={handleProviderChange}
              saving={providerSaving}
              error={providerSaveError}
            />

            {llmProvider === 'openrouter' ? (
              <OpenRouterSettings
                settings={settings}
                models={models}
                modelsLoading={modelsLoading}
                apiKey={openrouterKey}
                onApiKeyChange={setOpenrouterKey}
                model={openrouterModel}
                onModelChange={setOpenrouterModel}
                writerModel={openrouterWriterModel}
                onWriterModelChange={setOpenrouterWriterModel}
              />
            ) : (
              <div className="card mb-4 sm:mb-6">
                <h3 className="mb-4 flex items-center gap-2 text-base font-semibold text-white sm:text-lg">
                  <Cpu className="h-5 w-5 flex-shrink-0 text-accent" />
                  Codex subscription
                </h3>
                <CodexSettings
                  model={codexModel}
                  onModelChange={handleCodexModelChange}
                  savingModel={providerSaving}
                />
              </div>
            )}

            <TtsSettings
              settings={settings}
              provider={ttsProvider}
              onProviderChange={setTtsProvider}
              piperUrl={piperUrl}
              onPiperUrlChange={setPiperUrl}
              elevenlabsKey={elevenlabsKey}
              onElevenlabsKeyChange={setElevenlabsKey}
              elevenlabsModel={elevenlabsModel}
              onElevenlabsModelChange={setElevenlabsModel}
              geminiKey={geminiKey}
              onGeminiKeyChange={setGeminiKey}
              geminiModel={geminiModel}
              onGeminiModelChange={setGeminiModel}
              enableNonSpeechSounds={enableNonSpeechSounds}
              onEnableNonSpeechSoundsChange={setEnableNonSpeechSounds}
              castCount={castSummary ? (castSummary.counts[ttsProvider] ?? 0) : undefined}
              providerLabel={providerLabel(castList?.providers ?? [], ttsProvider)}
              onOpenCasts={() => navigate('/casts')}
            />
          </SettingsGroup>

          {/* Content */}
          <SettingsGroup
            id={CONTENT_GROUP.id}
            title={CONTENT_GROUP.label}
            description="How long briefings run, how they sound, and where news comes from."
          >
            <ContentSettings
              durationSlider={briefingDurationSlider}
              onDurationSliderChange={setBriefingDurationSlider}
              complexity={conversationComplexity}
              onComplexityChange={setConversationComplexity}
            />

            {/* News Sources Section */}
            <div className="card mb-4 sm:mb-6">
              <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
                <Rss className="w-5 h-5 text-accent" />
                News Sources
              </h3>

              <div>
                <label className="label">NewsAPI Key (optional)</label>
                <SecretInput
                  value={newsApiKey}
                  onChange={setNewsApiKey}
                  placeholder={settings?.news_api_key || 'Enter NewsAPI key'}
                />
              </div>
            </div>
          </SettingsGroup>

          {/* App */}
          <SettingsGroup
            id={APP_GROUP.id}
            title={APP_GROUP.label}
            description="Playback, time, notifications, and more."
          >
            {/* Playback Section */}
            <div className="card mb-4 sm:mb-6">
              <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
                <SettingsIcon className="w-5 h-5 text-accent" />
                Playback
              </h3>

              <SettingsCheckbox
                checked={autoPlayNext}
                onChange={setAutoPlayNext}
                title="Auto-play Next Briefing"
                description="When a briefing finishes, automatically play the most recent unlistened briefing."
              />
            </div>

            {/* Timezone Section */}
            <div className="card mb-4 sm:mb-6">
              <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
                <Globe className="w-5 h-5 text-accent" />
                Timezone
              </h3>

              <div>
                <label className="label">Your Timezone</label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="input"
                >
                  {timezones && Object.entries(timezones).map(([region, tzList]) => (
                    <optgroup key={region} label={region}>
                      {tzList.map((tz) => (
                        <option key={tz.id} value={tz.id}>
                          {tz.name} ({tz.offset})
                        </option>
                      ))}
                    </optgroup>
                  ))}
                  {!timezones && (
                    <option value="UTC">UTC (Coordinated Universal Time)</option>
                  )}
                </select>
              </div>
            </div>

            {/* Email Notifications Section */}
            <div className="card mb-4 sm:mb-6">
              <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2 flex-wrap">
                <Mail className="w-5 h-5 text-accent flex-shrink-0" />
                <span>Email Notifications (Resend)</span>
                {settings?.resend_configured ? (
                  <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">
                    Configured
                  </span>
                ) : (
                  <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
                    Not configured
                  </span>
                )}
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="label">Resend API Key</label>
                  <SecretInput
                    value={resendApiKey}
                    onChange={setResendApiKey}
                    placeholder={settings?.resend_api_key || 're_xxxxxxxxxxxxxxxxxxxxx'}
                  />
                </div>

                <div>
                  <label className="label">From Email Address</label>
                  <div className="relative">
                    <Mail className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 sm:w-5 h-4 sm:h-5 text-augustus-500" />
                    <input
                      type="email"
                      value={resendFromEmail}
                      onChange={(e) => setResendFromEmail(e.target.value)}
                      placeholder={settings?.resend_from_email || 'onboarding@resend.dev'}
                      className="input pl-10 sm:pl-12"
                    />
                  </div>
                  <p className="text-xs text-augustus-500 mt-1">
                    Email address to send from. Leave blank to use the default (onboarding@resend.dev).
                  </p>
                </div>
              </div>
            </div>

            {/* Link cards */}
            <div className="mt-6 sm:mt-8 space-y-4">
              <SettingsLinkCard
                icon={Plug}
                title="MCP"
                description="Connect AI agents like Claude Desktop, Claude Code, or Cursor to Augustus"
                onClick={() => navigate('/mcp')}
              />
              <SettingsLinkCard
                icon={Info}
                title="About Augustus"
                description="Learn more about the app, server, and creator"
                onClick={() => navigate('/about')}
              />
              <SettingsLinkCard
                icon={Sparkles}
                title="Start Onboarding"
                description="Complete the setup wizard to configure your AI providers, topics, and generate your first podcast"
                onClick={restartOnboarding}
              />
            </div>
          </SettingsGroup>
        </>
      )}
    </div>
  )
}
