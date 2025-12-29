import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  Sparkles,
  ChevronRight,
  ChevronLeft,
  User,
  Key,
  Volume2,
  Tag,
  Check,
  Loader2,
  Podcast,
  ExternalLink,
  Eye,
  EyeOff,
  Info,
  Play,
  Zap,
  Brain,
  Search,
  ChevronDown,
  CheckCircle,
  XCircle,
  Globe,
} from 'lucide-react'
import { settingsApi, topicsApi, briefingsApi, ModelOption } from '../api/client'

// Step definitions
const STEPS = [
  { id: 'welcome', title: 'Welcome', icon: User },
  { id: 'api-key', title: 'AI Provider', icon: Key },
  { id: 'tts', title: 'Voice Engine', icon: Volume2 },
  { id: 'topics', title: 'Interests', icon: Tag },
  { id: 'confirm', title: 'First Podcast', icon: Check },
  { id: 'generate', title: 'Creating...', icon: Sparkles },
]

// Generic topics users can choose from
const GENERIC_TOPICS = [
  { name: 'US News', description: 'Breaking news from the United States', color: '#3B82F6', useNewsapi: true },
  { name: 'World News', description: 'Global headlines and international affairs', color: '#10B981', useNewsapi: true },
  { name: 'Business', description: 'Markets, finance, and corporate news', color: '#F59E0B', useNewsapi: true },
  { name: 'Technology', description: 'Tech industry and digital trends', color: '#8B5CF6', useNewsapi: true },
  { name: 'Science', description: 'Scientific discoveries and research', color: '#EC4899', useNewsapi: true },
  { name: 'Health', description: 'Medical news and wellness updates', color: '#EF4444', useNewsapi: true },
  { name: 'Sports', description: 'Scores, highlights, and sports news', color: '#06B6D4', useNewsapi: true },
  { name: 'Entertainment', description: 'Movies, music, and celebrity news', color: '#F97316', useNewsapi: true },
  { name: 'Politics', description: 'Political developments and policy', color: '#6366F1', useNewsapi: true },
  { name: 'Climate', description: 'Environmental and climate news', color: '#84CC16', useNewsapi: true },
]

interface TopicSelection {
  name: string
  description: string
  color: string
  useNewsapi: boolean
}

interface OnboardingData {
  userName: string
  timezone: string
  openrouterApiKey: string
  generalModel: string
  writerModel: string
  ttsProvider: 'gemini' | 'elevenlabs' | 'piper'
  geminiApiKey: string
  elevenlabsApiKey: string
  selectedTopics: TopicSelection[]
  customTopicPrompt: string
  firstBriefingTopics: string[]
}

// ============ Welcome Step ============
function WelcomeStep({
  userName,
  timezone,
  onUpdate,
  onNext,
  onSkip,
  isLoading = false,
}: {
  userName: string
  timezone: string
  onUpdate: (updates: { userName?: string; timezone?: string }) => void
  onNext: () => void
  onSkip: () => void
  isLoading?: boolean
}) {
  // Fetch available timezones
  const { data: timezones } = useQuery({
    queryKey: ['timezones'],
    queryFn: () => settingsApi.getTimezones(),
  })

  return (
    <div className="w-full max-w-lg space-y-8 text-center">
      {/* Skip link at top */}
      <div className="flex justify-end">
        <button
          onClick={onSkip}
          className="text-sm text-augustus-400 hover:text-augustus-300 transition-colors"
        >
          Skip for now
        </button>
      </div>

      <div className="space-y-4">
        <div className="w-20 h-20 mx-auto bg-gradient-to-br from-accent to-accent-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-accent/30">
          <Podcast className="w-10 h-10 text-white" />
        </div>
        <h1 className="text-3xl sm:text-4xl font-display font-bold text-white">
          Welcome to Augustus
        </h1>
        <p className="text-augustus-400 text-lg">
          Your AI-powered personalized news podcast
        </p>
      </div>

      <div className="space-y-4 text-left">
        <div>
          <label className="label text-base">What should we call you?</label>
          <input
            type="text"
            value={userName}
            onChange={(e) => onUpdate({ userName: e.target.value })}
            placeholder="Enter your name"
            className="input text-lg"
            autoFocus
            onKeyDown={(e) => e.key === 'Enter' && userName.trim() && onNext()}
          />
          <p className="text-sm text-augustus-500">
            Your hosts will greet you by name in each podcast
          </p>
        </div>

        <div>
          <label className="label text-base flex items-center gap-2">
            <Globe className="w-4 h-4 text-augustus-400" />
            Your Timezone
          </label>
          <select
            value={timezone}
            onChange={(e) => onUpdate({ timezone: e.target.value })}
            className="input text-lg"
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
              <option value={timezone || 'UTC'}>
                {timezone || 'UTC (Coordinated Universal Time)'}
              </option>
            )}
          </select>
          <p className="text-sm text-augustus-500">
            Used for scheduling and displaying times in your local timezone
          </p>
        </div>
      </div>

      <button
        onClick={onNext}
        disabled={!userName.trim() || isLoading}
        className="btn btn-primary w-full text-lg py-4"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Saving...
          </>
        ) : (
          <>
            Get Started <ChevronRight className="w-5 h-5" />
          </>
        )}
      </button>
    </div>
  )
}

// ============ API Key Step ============
function ApiKeyStep({
  apiKey,
  generalModel,
  writerModel,
  onUpdate,
  onNext,
  onBack,
}: {
  apiKey: string
  generalModel: string
  writerModel: string
  onUpdate: (updates: Partial<{ openrouterApiKey: string; generalModel: string; writerModel: string }>) => void
  onNext: () => void
  onBack: () => void
}) {
  const [showKey, setShowKey] = useState(false)
  const [showGeneralDropdown, setShowGeneralDropdown] = useState(false)
  const [showWriterDropdown, setShowWriterDropdown] = useState(false)
  const [generalSearch, setGeneralSearch] = useState('')
  const [writerSearch, setWriterSearch] = useState('')
  const [keyValidation, setKeyValidation] = useState<{ valid: boolean | null; message: string }>({ valid: null, message: '' })
  const [isValidating, setIsValidating] = useState(false)
  const validationTimeoutRef = useRef<ReturnType<typeof setTimeout>>()

  // Validate API key when it changes (debounced)
  useEffect(() => {
    // Clear previous timeout
    if (validationTimeoutRef.current) {
      clearTimeout(validationTimeoutRef.current)
    }

    // Reset validation state if key is too short
    if (apiKey.length < 10) {
      setKeyValidation({ valid: null, message: '' })
      return
    }

    // Debounce validation
    setIsValidating(true)
    validationTimeoutRef.current = setTimeout(async () => {
      try {
        const result = await settingsApi.validateOpenRouterKey(apiKey)
        setKeyValidation(result)
      } catch (error) {
        setKeyValidation({ valid: false, message: 'Failed to validate API key' })
      } finally {
        setIsValidating(false)
      }
    }, 1000) // Wait 1 second after user stops typing

    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current)
      }
    }
  }, [apiKey])

  // Fetch models when API key is valid
  const { data: models, isLoading: modelsLoading, refetch } = useQuery({
    queryKey: ['models'],
    queryFn: () => settingsApi.getModels(),
    enabled: apiKey.length > 10 && keyValidation.valid === true,
    staleTime: 1000 * 60 * 5,
  })

  // Refetch when API key is validated
  useEffect(() => {
    if (apiKey.length > 10 && keyValidation.valid === true) {
      refetch()
    }
  }, [apiKey, keyValidation.valid, refetch])

  // Filter and group models
  const recommendedGeneralModels = useMemo(() => {
    if (!models) return []
    // Prioritize Gemini Flash 3.0, then other fast models
    const geminiFlash30 = models.find(m => 
      m.id.includes('gemini-3.0-flash') || 
      m.id.includes('gemini-3-flash') ||
      m.id.includes('gemini-flash-3')
    )
    const otherFastModels = models.filter(m =>
      (m.id.includes('flash') && !m.id.includes('gemini-3')) ||
      m.id.includes('haiku') ||
      m.id.includes('gpt-4o-mini') ||
      m.id.includes('gemini-2.0-flash')
    )
    
    const result = geminiFlash30 ? [geminiFlash30, ...otherFastModels] : otherFastModels
    return result.slice(0, 6)
  }, [models])

  const recommendedWriterModels = useMemo(() => {
    if (!models) return []
    // Prioritize Gemini 3 Pro, then other thinking/quality models
    const gemini3Pro = models.find(m => 
      m.id.includes('gemini-3.0-pro') || 
      m.id.includes('gemini-3-pro') ||
      m.id.includes('gemini-pro-3')
    )
    const otherWriterModels = models.filter(m =>
      m.id.includes('thinking') ||
      m.id.includes('sonnet') ||
      m.id.includes('opus') ||
      m.id.includes('o1') ||
      m.id.includes('deepseek-r1') ||
      m.id.includes('gemini-2.0-flash-thinking') ||
      (m.id.includes('pro') && !m.id.includes('prov') && !m.id.includes('gemini-3'))
    )
    
    const result = gemini3Pro ? [gemini3Pro, ...otherWriterModels] : otherWriterModels
    return result.slice(0, 6)
  }, [models])

  const filteredGeneralModels = useMemo(() => {
    if (!models) return []
    if (!generalSearch.trim()) return models
    const search = generalSearch.toLowerCase()
    return models.filter(m =>
      m.name.toLowerCase().includes(search) ||
      m.id.toLowerCase().includes(search) ||
      m.provider.toLowerCase().includes(search)
    )
  }, [models, generalSearch])

  const filteredWriterModels = useMemo(() => {
    if (!models) return []
    if (!writerSearch.trim()) return models
    const search = writerSearch.toLowerCase()
    return models.filter(m =>
      m.name.toLowerCase().includes(search) ||
      m.id.toLowerCase().includes(search) ||
      m.provider.toLowerCase().includes(search)
    )
  }, [models, writerSearch])

  const groupedGeneralModels = useMemo(() => {
    const groups: Record<string, ModelOption[]> = {}
    for (const model of filteredGeneralModels) {
      if (!groups[model.provider]) groups[model.provider] = []
      groups[model.provider].push(model)
    }
    return groups
  }, [filteredGeneralModels])

  const groupedWriterModels = useMemo(() => {
    const groups: Record<string, ModelOption[]> = {}
    for (const model of filteredWriterModels) {
      if (!groups[model.provider]) groups[model.provider] = []
      groups[model.provider].push(model)
    }
    return groups
  }, [filteredWriterModels])

  const selectedGeneralModel = models?.find(m => m.id === generalModel)
  const selectedWriterModel = models?.find(m => m.id === writerModel)

  return (
    <div className="w-full max-w-lg space-y-6">
      <div className="text-center mb-8">
        <Key className="w-12 h-12 text-accent mx-auto mb-4" />
        <h2 className="text-2xl font-display font-bold text-white mb-2">
          Connect Your AI
        </h2>
        <p className="text-augustus-400">
          Augustus uses OpenRouter to access AI models
        </p>
      </div>

      {/* API Key Input */}
      <div className="space-y-3">
        <label className="label">OpenRouter API Key</label>
        <div className="relative">
          <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-augustus-500" />
          <input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => onUpdate({ openrouterApiKey: e.target.value })}
            placeholder="sk-or-v1-..."
            className={clsx(
              'input pl-12 pr-12',
              keyValidation.valid === true && 'border-green-500',
              keyValidation.valid === false && 'border-red-500'
            )}
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
            {isValidating && (
              <Loader2 className="w-5 h-5 animate-spin text-augustus-500" />
            )}
            {!isValidating && keyValidation.valid === true && (
              <CheckCircle className="w-5 h-5 text-green-500" />
            )}
            {!isValidating && keyValidation.valid === false && (
              <XCircle className="w-5 h-5 text-red-500" />
            )}
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="text-augustus-500 hover:text-augustus-300"
            >
              {showKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>
        {keyValidation.message && (
          <p className={clsx(
            'text-sm flex items-center gap-2',
            keyValidation.valid === true ? 'text-green-400' : 'text-red-400'
          )}>
            {keyValidation.valid === true ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <XCircle className="w-4 h-4" />
            )}
            {keyValidation.message}
          </p>
        )}
        <div className="flex items-center gap-2 text-sm text-augustus-400">
          <ExternalLink className="w-4 h-4" />
          <a
            href="https://openrouter.ai/keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            Get your OpenRouter API key →
          </a>
        </div>
      </div>

      {/* Model Selection - appears after API key is entered */}
      {apiKey.length > 10 && (
        <div className="space-y-6 pt-4 border-t border-augustus-800 animate-in fade-in duration-300">
          {modelsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-accent" />
              <span className="ml-2 text-augustus-400">Loading models...</span>
            </div>
          ) : (
            <>
              {/* Model tips - at the top */}
              <div className="p-3 bg-augustus-800/50 rounded-lg">
                <div className="flex items-start gap-2 text-xs text-augustus-400">
                  <Info className="w-4 h-4 flex-shrink-0 mt-0.5 text-accent" />
                  <div>
                    <p className="font-medium text-augustus-300 mb-1">Model Tips:</p>
                    <ul className="space-y-1 list-disc list-inside">
                      <li><strong>General:</strong> Gemini Flash 3.0, Claude Haiku — fast & affordable</li>
                      <li><strong>Writer:</strong> Gemini 3 Pro, Claude Sonnet — better quality scripts</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* General Model Selection */}
              <div className="space-y-3">
                <div>
                  <label className="label flex items-center gap-2">
                    <Zap className="w-4 h-4 text-yellow-400" />
                    General Model
                  </label>
                  <p className="text-xs text-augustus-500 mb-2">
                    Fast model for analysis & research
                  </p>
                </div>

                {/* Quick recommendations */}
                <div className="flex flex-wrap gap-2 mb-2">
                  {recommendedGeneralModels.map((model) => {
                    const isGeminiFlash30 = model.id.includes('gemini-3.0-flash') || 
                                           model.id.includes('gemini-3-flash') ||
                                           model.id.includes('gemini-flash-3')
                    return (
                      <button
                        key={model.id}
                        onClick={() => onUpdate({ generalModel: model.id })}
                        className={clsx(
                          'px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5',
                          generalModel === model.id
                            ? 'bg-accent text-white'
                            : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                        )}
                      >
                        {model.name}
                        {isGeminiFlash30 && (
                          <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-[10px] font-semibold">
                            Recommended
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>

                {/* Selected model display / dropdown trigger */}
                <button
                  type="button"
                  onClick={() => setShowGeneralDropdown(!showGeneralDropdown)}
                  className="input w-full text-left flex items-center justify-between"
                >
                  <span className={selectedGeneralModel ? 'text-white' : 'text-augustus-500'}>
                    {selectedGeneralModel?.name || 'Select a model...'}
                  </span>
                  <ChevronDown className={clsx('w-5 h-5 text-augustus-500 transition-transform', showGeneralDropdown && 'rotate-180')} />
                </button>

                {/* General Model Dropdown */}
                {showGeneralDropdown && (
                  <div className="relative z-20">
                    <div className="absolute top-0 left-0 right-0 bg-augustus-900 border border-augustus-700 rounded-lg shadow-2xl max-h-64 overflow-hidden">
                      <div className="p-2 border-b border-augustus-700">
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-augustus-500" />
                          <input
                            type="text"
                            value={generalSearch}
                            onChange={(e) => setGeneralSearch(e.target.value)}
                            placeholder="Search models..."
                            className="w-full pl-9 pr-4 py-2 bg-augustus-800 border border-augustus-700 rounded-lg text-white text-sm"
                            autoFocus
                          />
                        </div>
                      </div>
                      <div className="overflow-y-auto max-h-48">
                        {Object.entries(groupedGeneralModels).map(([provider, providerModels]) => (
                          <div key={provider}>
                            <div className="px-3 py-1.5 bg-augustus-800/50 text-xs font-semibold text-augustus-400 uppercase">
                              {provider}
                            </div>
                            {providerModels.map((model) => (
                              <button
                                key={model.id}
                                onClick={() => {
                                  onUpdate({ generalModel: model.id })
                                  setShowGeneralDropdown(false)
                                  setGeneralSearch('')
                                }}
                                className={clsx(
                                  'w-full px-3 py-2 text-left hover:bg-augustus-800 transition-colors text-sm',
                                  model.id === generalModel && 'bg-accent/10 text-accent'
                                )}
                              >
                                {model.name}
                              </button>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Writer Model Selection */}
              <div className="space-y-3">
                <div>
                  <label className="label flex items-center gap-2">
                    <Brain className="w-4 h-4 text-purple-400" />
                    Writer Model
                  </label>
                  <p className="text-xs text-augustus-500 mb-2">
                    For crafting podcast scripts (thinking models recommended)
                  </p>
                </div>

                {/* Quick recommendations */}
                <div className="flex flex-wrap gap-2 mb-2">
                  {recommendedWriterModels.map((model) => {
                    const isGemini3Pro = model.id.includes('gemini-3.0-pro') || 
                                        model.id.includes('gemini-3-pro') ||
                                        model.id.includes('gemini-pro-3')
                    return (
                      <button
                        key={model.id}
                        onClick={() => onUpdate({ writerModel: model.id })}
                        className={clsx(
                          'px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5',
                          writerModel === model.id
                            ? 'bg-accent text-white'
                            : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                        )}
                      >
                        {model.name}
                        {isGemini3Pro && (
                          <span className="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded text-[10px] font-semibold">
                            Recommended
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>

                {/* Selected model display / dropdown trigger */}
                <button
                  type="button"
                  onClick={() => setShowWriterDropdown(!showWriterDropdown)}
                  className="input w-full text-left flex items-center justify-between"
                >
                  <span className={selectedWriterModel ? 'text-white' : 'text-augustus-500'}>
                    {selectedWriterModel?.name || 'Select a model...'}
                  </span>
                  <ChevronDown className={clsx('w-5 h-5 text-augustus-500 transition-transform', showWriterDropdown && 'rotate-180')} />
                </button>

                {/* Writer Model Dropdown */}
                {showWriterDropdown && (
                  <div className="relative z-10">
                    <div className="absolute top-0 left-0 right-0 bg-augustus-900 border border-augustus-700 rounded-lg shadow-2xl max-h-64 overflow-hidden">
                      <div className="p-2 border-b border-augustus-700">
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-augustus-500" />
                          <input
                            type="text"
                            value={writerSearch}
                            onChange={(e) => setWriterSearch(e.target.value)}
                            placeholder="Search models..."
                            className="w-full pl-9 pr-4 py-2 bg-augustus-800 border border-augustus-700 rounded-lg text-white text-sm"
                            autoFocus
                          />
                        </div>
                      </div>
                      <div className="overflow-y-auto max-h-48">
                        {Object.entries(groupedWriterModels).map(([provider, providerModels]) => (
                          <div key={provider}>
                            <div className="px-3 py-1.5 bg-augustus-800/50 text-xs font-semibold text-augustus-400 uppercase">
                              {provider}
                            </div>
                            {providerModels.map((model) => (
                              <button
                                key={model.id}
                                onClick={() => {
                                  onUpdate({ writerModel: model.id })
                                  setShowWriterDropdown(false)
                                  setWriterSearch('')
                                }}
                                className={clsx(
                                  'w-full px-3 py-2 text-left hover:bg-augustus-800 transition-colors text-sm',
                                  model.id === writerModel && 'bg-accent/10 text-accent'
                                )}
                              >
                                {model.name}
                              </button>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex gap-3 pt-4">
        <button onClick={onBack} className="btn btn-ghost flex-1">
          <ChevronLeft className="w-5 h-5" /> Back
        </button>
        <button
          onClick={onNext}
          disabled={!apiKey || keyValidation.valid !== true || !generalModel || !writerModel || isLoading}
          className="btn btn-primary flex-1"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              Continue <ChevronRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}

// ============ TTS Provider Step ============
function TTSProviderStep({
  provider,
  geminiKey,
  elevenlabsKey,
  onUpdate,
  onNext,
  onBack,
  isLoading = false,
}: {
  provider: 'gemini' | 'elevenlabs' | 'piper'
  geminiKey: string
  elevenlabsKey: string
  onUpdate: (updates: Partial<{ ttsProvider: 'gemini' | 'elevenlabs' | 'piper'; geminiApiKey: string; elevenlabsApiKey: string }>) => void
  onNext: () => void
  onBack: () => void
  isLoading?: boolean
}) {
  const [showGeminiKey, setShowGeminiKey] = useState(false)
  const [showElevenlabsKey, setShowElevenlabsKey] = useState(false)
  const [geminiValidation, setGeminiValidation] = useState<{ valid: boolean | null; message: string }>({ valid: null, message: '' })
  const [elevenlabsValidation, setElevenlabsValidation] = useState<{ valid: boolean | null; message: string }>({ valid: null, message: '' })
  const [isValidatingGemini, setIsValidatingGemini] = useState(false)
  const [isValidatingElevenlabs, setIsValidatingElevenlabs] = useState(false)
  const geminiTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const elevenlabsTimeoutRef = useRef<ReturnType<typeof setTimeout>>()

  // Validate Gemini key when it changes (debounced)
  useEffect(() => {
    if (geminiTimeoutRef.current) {
      clearTimeout(geminiTimeoutRef.current)
    }

    if (geminiKey.length < 10) {
      setGeminiValidation({ valid: null, message: '' })
      return
    }

    setIsValidatingGemini(true)
    geminiTimeoutRef.current = setTimeout(async () => {
      try {
        const result = await settingsApi.validateGeminiKey(geminiKey)
        setGeminiValidation(result)
      } catch (error) {
        setGeminiValidation({ valid: false, message: 'Failed to validate API key' })
      } finally {
        setIsValidatingGemini(false)
      }
    }, 1000)

    return () => {
      if (geminiTimeoutRef.current) {
        clearTimeout(geminiTimeoutRef.current)
      }
    }
  }, [geminiKey])

  // Validate ElevenLabs key when it changes (debounced)
  useEffect(() => {
    if (elevenlabsTimeoutRef.current) {
      clearTimeout(elevenlabsTimeoutRef.current)
    }

    if (elevenlabsKey.length < 10) {
      setElevenlabsValidation({ valid: null, message: '' })
      return
    }

    setIsValidatingElevenlabs(true)
    elevenlabsTimeoutRef.current = setTimeout(async () => {
      try {
        const result = await settingsApi.validateElevenLabsKey(elevenlabsKey)
        setElevenlabsValidation(result)
      } catch (error) {
        setElevenlabsValidation({ valid: false, message: 'Failed to validate API key' })
      } finally {
        setIsValidatingElevenlabs(false)
      }
    }, 1000)

    return () => {
      if (elevenlabsTimeoutRef.current) {
        clearTimeout(elevenlabsTimeoutRef.current)
      }
    }
  }, [elevenlabsKey])

  const canContinue = provider === 'piper' || 
    (provider === 'gemini' && geminiKey && geminiValidation.valid === true) || 
    (provider === 'elevenlabs' && elevenlabsKey && elevenlabsValidation.valid === true)

  return (
    <div className="w-full max-w-lg space-y-6">
      <div className="text-center mb-8">
        <Volume2 className="w-12 h-12 text-accent mx-auto mb-4" />
        <h2 className="text-2xl font-display font-bold text-white mb-2">
          Choose Your Voice Engine
        </h2>
        <p className="text-augustus-400">
          Select how Augustus will read your podcasts
        </p>
      </div>

      <div className="space-y-3">
        {/* Google Gemini - Recommended */}
        <button
          onClick={() => onUpdate({ ttsProvider: 'gemini' })}
          className={clsx(
            'w-full p-4 rounded-xl border-2 text-left transition-all',
            provider === 'gemini'
              ? 'border-accent bg-accent/10'
              : 'border-augustus-700 hover:border-augustus-600'
          )}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-green-500 flex items-center justify-center text-white font-bold">
              G
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">Google Gemini</span>
                <span className="px-2 py-0.5 bg-accent/20 text-accent text-xs rounded-full">Recommended</span>
              </div>
              <p className="text-sm text-augustus-400">Natural multi-speaker voices, free tier available</p>
            </div>
          </div>
        </button>

        {/* ElevenLabs */}
        <button
          onClick={() => onUpdate({ ttsProvider: 'elevenlabs' })}
          className={clsx(
            'w-full p-4 rounded-xl border-2 text-left transition-all',
            provider === 'elevenlabs'
              ? 'border-accent bg-accent/10'
              : 'border-augustus-700 hover:border-augustus-600'
          )}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-sm">
              11
            </div>
            <div className="flex-1">
              <span className="font-semibold text-white">ElevenLabs</span>
              <p className="text-sm text-augustus-400">Premium ultra-realistic voices</p>
            </div>
          </div>
        </button>

        {/* Piper (Self-hosted) */}
        <button
          onClick={() => onUpdate({ ttsProvider: 'piper' })}
          className={clsx(
            'w-full p-4 rounded-xl border-2 text-left transition-all',
            provider === 'piper'
              ? 'border-accent bg-accent/10'
              : 'border-augustus-700 hover:border-augustus-600'
          )}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-gray-600 to-gray-800 flex items-center justify-center text-white font-bold">
              P
            </div>
            <div className="flex-1">
              <span className="font-semibold text-white">Piper</span>
              <p className="text-sm text-augustus-400">Self-hosted, free, requires setup</p>
            </div>
          </div>
        </button>
      </div>

      {/* API Key input based on selection */}
      {provider === 'gemini' && (
        <div className="space-y-3 p-4 bg-augustus-800/50 rounded-xl animate-in fade-in duration-200">
          <label className="label">Gemini API Key</label>
          <div className="relative">
            <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-augustus-500" />
            <input
              type={showGeminiKey ? 'text' : 'password'}
              value={geminiKey}
              onChange={(e) => onUpdate({ geminiApiKey: e.target.value })}
              placeholder="AIza..."
              className={clsx(
                'input pl-12 pr-12',
                geminiValidation.valid === true && 'border-green-500',
                geminiValidation.valid === false && 'border-red-500'
              )}
            />
            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
              {isValidatingGemini && (
                <Loader2 className="w-5 h-5 animate-spin text-augustus-500" />
              )}
              {!isValidatingGemini && geminiValidation.valid === true && (
                <CheckCircle className="w-5 h-5 text-green-500" />
              )}
              {!isValidatingGemini && geminiValidation.valid === false && (
                <XCircle className="w-5 h-5 text-red-500" />
              )}
              <button
                type="button"
                onClick={() => setShowGeminiKey(!showGeminiKey)}
                className="text-augustus-500 hover:text-augustus-300"
              >
                {showGeminiKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>
          {geminiValidation.message && (
            <p className={clsx(
              'text-sm flex items-center gap-2',
              geminiValidation.valid === true ? 'text-green-400' : 'text-red-400'
            )}>
              {geminiValidation.valid === true ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
              {geminiValidation.message}
            </p>
          )}
          <div className="flex items-center gap-2 text-sm text-augustus-400">
            <ExternalLink className="w-4 h-4" />
            <a
              href="https://aistudio.google.com/apikey"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              Get your free Gemini API key →
            </a>
          </div>
          <p className="text-xs text-augustus-500">
            1. Click the link → 2. Sign in with Google → 3. Create API Key → 4. Paste here
          </p>
        </div>
      )}

      {provider === 'elevenlabs' && (
        <div className="space-y-3 p-4 bg-augustus-800/50 rounded-xl animate-in fade-in duration-200">
          <label className="label">ElevenLabs API Key</label>
          <div className="relative">
            <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-augustus-500" />
            <input
              type={showElevenlabsKey ? 'text' : 'password'}
              value={elevenlabsKey}
              onChange={(e) => onUpdate({ elevenlabsApiKey: e.target.value })}
              placeholder="sk_..."
              className={clsx(
                'input pl-12 pr-12',
                elevenlabsValidation.valid === true && 'border-green-500',
                elevenlabsValidation.valid === false && 'border-red-500'
              )}
            />
            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
              {isValidatingElevenlabs && (
                <Loader2 className="w-5 h-5 animate-spin text-augustus-500" />
              )}
              {!isValidatingElevenlabs && elevenlabsValidation.valid === true && (
                <CheckCircle className="w-5 h-5 text-green-500" />
              )}
              {!isValidatingElevenlabs && elevenlabsValidation.valid === false && (
                <XCircle className="w-5 h-5 text-red-500" />
              )}
              <button
                type="button"
                onClick={() => setShowElevenlabsKey(!showElevenlabsKey)}
                className="text-augustus-500 hover:text-augustus-300"
              >
                {showElevenlabsKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>
          {elevenlabsValidation.message && (
            <p className={clsx(
              'text-sm flex items-center gap-2',
              elevenlabsValidation.valid === true ? 'text-green-400' : 'text-red-400'
            )}>
              {elevenlabsValidation.valid === true ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
              {elevenlabsValidation.message}
            </p>
          )}
          <div className="flex items-center gap-2 text-sm text-augustus-400">
            <ExternalLink className="w-4 h-4" />
            <a
              href="https://elevenlabs.io/app/settings/api-keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              Get your ElevenLabs API key →
            </a>
          </div>
        </div>
      )}

      {provider === 'piper' && (
        <div className="p-4 bg-augustus-800/50 rounded-xl">
          <p className="text-sm text-augustus-400">
            Piper is a self-hosted TTS solution. You can configure it later in Settings.
          </p>
        </div>
      )}

      {/* Navigation */}
      <div className="flex gap-3 pt-4">
        <button onClick={onBack} className="btn btn-ghost flex-1">
          <ChevronLeft className="w-5 h-5" /> Back
        </button>
        <button
          onClick={onNext}
          disabled={!canContinue || isLoading}
          className="btn btn-primary flex-1"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              Continue <ChevronRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}

// ============ Topics Step ============
function TopicsStep({
  selectedTopics,
  customPrompt,
  onUpdate,
  onNext,
  onBack,
}: {
  selectedTopics: TopicSelection[]
  customPrompt: string
  onUpdate: (topics: TopicSelection[], prompt: string) => void
  onNext: () => void
  onBack: () => void
}) {
  const [isGeneratingCustom, setIsGeneratingCustom] = useState(false)
  
  // Lazy-load trending topics from the LLM
  const {
    data: trendingTopics,
    isLoading: trendingLoading,
    error: trendingError,
    refetch: refetchTrending,
  } = useQuery({
    queryKey: ['trending-topics'],
    queryFn: () => topicsApi.generateTrending(5),
    staleTime: 1000 * 60 * 10,
    retry: 2,
  })

  const toggleTopic = (topic: { name: string; description: string; color: string }) => {
    const exists = selectedTopics.find(t => t.name === topic.name)
    if (exists) {
      onUpdate(selectedTopics.filter(t => t.name !== topic.name), customPrompt)
    } else {
      onUpdate([...selectedTopics, { ...topic, useNewsapi: true }], customPrompt)
    }
  }

  const handleGenerateCustom = async () => {
    if (!customPrompt.trim() || isGeneratingCustom) return
    
    setIsGeneratingCustom(true)
    try {
      const generated = await topicsApi.generateFromPrompt(customPrompt.trim())
      // Add the generated topic to selected topics
      const newTopic: TopicSelection = {
        name: generated.name,
        description: generated.description,
        color: GENERIC_TOPICS[Math.floor(Math.random() * GENERIC_TOPICS.length)].color,
        useNewsapi: generated.use_newsapi,
      }
      // Check if topic already exists
      const exists = selectedTopics.find(t => t.name === newTopic.name)
      if (!exists) {
        onUpdate([...selectedTopics, newTopic], '') // Clear prompt after adding
      } else {
        onUpdate(selectedTopics, '') // Just clear prompt if already exists
      }
    } catch (error) {
      console.error('Failed to generate topic:', error)
      // Keep the prompt so user can try again
    } finally {
      setIsGeneratingCustom(false)
    }
  }

  return (
    <div className="w-full max-w-2xl space-y-6">
      <div className="text-center mb-6">
        <Tag className="w-12 h-12 text-accent mx-auto mb-4" />
        <h2 className="text-2xl font-display font-bold text-white mb-2">
          What interests you?
        </h2>
        <p className="text-augustus-400">
          Select topics for your daily podcasts (select at least 3)
        </p>
      </div>

      {/* Generic Topics */}
      <div>
        <h3 className="text-sm font-semibold text-augustus-400 uppercase tracking-wide mb-3">
          Popular Topics
        </h3>
        <div className="flex flex-wrap gap-2">
          {GENERIC_TOPICS.map((topic) => {
            const isSelected = selectedTopics.some(t => t.name === topic.name)
            return (
              <button
                key={topic.name}
                onClick={() => toggleTopic(topic)}
                className={clsx(
                  'px-4 py-2 rounded-full text-sm font-medium transition-all flex items-center gap-2',
                  isSelected
                    ? 'text-white shadow-lg'
                    : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                )}
                style={isSelected ? { backgroundColor: topic.color } : undefined}
              >
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: topic.color }} />
                {topic.name}
              </button>
            )
          })}
        </div>
      </div>

      {/* Trending Topics - Lazy Loaded from LLM */}
      <div>
        <h3 className="text-sm font-semibold text-augustus-400 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-yellow-400" />
          Trending Right Now
          {trendingLoading && <Loader2 className="w-4 h-4 animate-spin text-augustus-500" />}
        </h3>

        {trendingLoading ? (
          <div className="flex gap-2 overflow-hidden">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="h-9 w-28 bg-augustus-700 rounded-full animate-pulse flex-shrink-0"
                style={{ animationDelay: `${i * 100}ms` }}
              />
            ))}
          </div>
        ) : trendingError ? (
          <div className="p-4 bg-augustus-800/30 rounded-xl">
            <p className="text-sm text-augustus-400 mb-2">Couldn't load trending topics</p>
            <button
              onClick={() => refetchTrending()}
              className="text-sm text-accent hover:underline"
            >
              Try again
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {trendingTopics?.map((topic) => {
              const isSelected = selectedTopics.some(t => t.name === topic.name)
              return (
                <button
                  key={topic.name}
                  onClick={() => toggleTopic(topic)}
                  className={clsx(
                    'px-4 py-2 rounded-full text-sm font-medium transition-all flex items-center gap-2 group relative',
                    isSelected
                      ? 'text-white shadow-lg'
                      : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                  )}
                  style={isSelected ? { backgroundColor: topic.color } : undefined}
                  title={topic.reasoning}
                >
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: topic.color }} />
                  {topic.name}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Custom Topic Input */}
      <div>
        <h3 className="text-sm font-semibold text-augustus-400 uppercase tracking-wide mb-3">
          ✨ Something else?
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={customPrompt}
            onChange={(e) => onUpdate(selectedTopics, e.target.value)}
            placeholder="e.g., Formula 1, Indie Games, Sustainable Fashion..."
            className="input flex-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && customPrompt.trim() && !isGeneratingCustom) {
                handleGenerateCustom()
              }
            }}
          />
          <button
            onClick={handleGenerateCustom}
            disabled={!customPrompt.trim() || isGeneratingCustom}
            className={clsx(
              'btn px-4',
              isGeneratingCustom ? 'btn-ghost' : 'btn-primary'
            )}
          >
            {isGeneratingCustom ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Sparkles className="w-5 h-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-augustus-500 mt-1">
          AI will create a custom topic with relevant sources
        </p>
      </div>

      {/* Custom Generated Topics */}
      {(() => {
        // Find topics that are in selectedTopics but not in GENERIC_TOPICS or trendingTopics
        const genericTopicNames = new Set(GENERIC_TOPICS.map(t => t.name))
        const trendingTopicNames = new Set(trendingTopics?.map(t => t.name) || [])
        const customTopics = selectedTopics.filter(
          topic => !genericTopicNames.has(topic.name) && !trendingTopicNames.has(topic.name)
        )

        if (customTopics.length === 0) return null

        return (
          <div>
            <h3 className="text-sm font-semibold text-augustus-400 uppercase tracking-wide mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              Your Custom Topics
            </h3>
            <div className="flex flex-wrap gap-2">
              {customTopics.map((topic) => {
                const isSelected = selectedTopics.some(t => t.name === topic.name)
                return (
                  <button
                    key={topic.name}
                    onClick={() => toggleTopic(topic)}
                    className={clsx(
                      'px-4 py-2 rounded-full text-sm font-medium transition-all flex items-center gap-2',
                      isSelected
                        ? 'text-white shadow-lg'
                        : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700'
                    )}
                    style={isSelected ? { backgroundColor: topic.color } : undefined}
                  >
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: topic.color }} />
                    {topic.name}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })()}

      {/* Selected count */}
      <div className="text-center text-sm text-augustus-400">
        {selectedTopics.length} topic{selectedTopics.length !== 1 ? 's' : ''} selected
        {selectedTopics.length < 3 && !customPrompt && (
          <span className="text-yellow-400"> (select at least 3)</span>
        )}
      </div>

      {/* Navigation */}
      <div className="flex gap-3 pt-4">
        <button onClick={onBack} className="btn btn-ghost flex-1">
          <ChevronLeft className="w-5 h-5" /> Back
        </button>
        <button
          onClick={onNext}
          disabled={selectedTopics.length < 3 && !customPrompt.trim()}
          className="btn btn-primary flex-1"
        >
          Continue <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}

// ============ Confirmation Step ============
function ConfirmationStep({
  selectedTopics,
  firstBriefingTopics,
  onUpdate,
  onComplete,
  onBack,
  isLoading,
}: {
  selectedTopics: TopicSelection[]
  firstBriefingTopics: string[]
  onUpdate: (topics: string[]) => void
  onComplete: () => void
  onBack: () => void
  isLoading: boolean
}) {
  // Default to first 3 topics if none selected
  useEffect(() => {
    if (firstBriefingTopics.length === 0 && selectedTopics.length > 0) {
      onUpdate(selectedTopics.slice(0, 3).map(t => t.name))
    }
  }, [])

  const toggleFirstBriefingTopic = (topicName: string) => {
    if (firstBriefingTopics.includes(topicName)) {
      onUpdate(firstBriefingTopics.filter(t => t !== topicName))
    } else {
      onUpdate([...firstBriefingTopics, topicName])
    }
  }

  return (
    <div className="w-full max-w-lg space-y-6">
      <div className="text-center mb-8">
        <Check className="w-12 h-12 text-accent mx-auto mb-4" />
        <h2 className="text-2xl font-display font-bold text-white mb-2">
          Ready for Your First Podcast!
        </h2>
        <p className="text-augustus-400">
          Choose which topics to include in your first briefing
        </p>
      </div>

      {/* Topics summary */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-augustus-400 uppercase tracking-wide">
          Your Topics ({selectedTopics.length})
        </h3>
        <div className="space-y-2">
          {selectedTopics.map((topic) => {
            const isSelected = firstBriefingTopics.includes(topic.name)
            return (
              <button
                key={topic.name}
                onClick={() => toggleFirstBriefingTopic(topic.name)}
                className={clsx(
                  'w-full p-3 rounded-lg border-2 text-left transition-all flex items-center gap-3',
                  isSelected
                    ? 'border-accent bg-accent/10'
                    : 'border-augustus-700 hover:border-augustus-600'
                )}
              >
                <div
                  className={clsx(
                    'w-5 h-5 rounded border-2 flex items-center justify-center transition-colors',
                    isSelected ? 'bg-accent border-accent' : 'border-augustus-600'
                  )}
                >
                  {isSelected && <Check className="w-3 h-3 text-white" />}
                </div>
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: topic.color }}
                />
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-white">{topic.name}</span>
                  <p className="text-xs text-augustus-400 truncate">{topic.description}</p>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {firstBriefingTopics.length === 0 && (
        <p className="text-sm text-yellow-400 text-center">
          Select at least one topic for your first podcast
        </p>
      )}

      {/* Generate button */}
      <button
        onClick={onComplete}
        disabled={isLoading || firstBriefingTopics.length === 0}
        className="btn btn-primary w-full text-lg py-4"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Creating your podcast...
          </>
        ) : (
          <>
            <Play className="w-5 h-5" />
            Create My First Podcast
          </>
        )}
      </button>

      <button onClick={onBack} disabled={isLoading} className="btn btn-ghost w-full">
        <ChevronLeft className="w-5 h-5" /> Back
      </button>
    </div>
  )
}

// ============ Generation Step ============
function GenerationStep() {
  const [dots, setDots] = useState('')

  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => (prev.length >= 3 ? '' : prev + '.'))
    }, 500)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="w-full max-w-lg space-y-8 text-center">
      <div className="space-y-6">
        <div className="relative">
          <div className="w-24 h-24 mx-auto bg-gradient-to-br from-accent to-accent-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-accent/30 animate-pulse">
            <Podcast className="w-12 h-12 text-white" />
          </div>
          <div className="absolute -top-2 -right-2 w-8 h-8 bg-yellow-400 rounded-full flex items-center justify-center animate-bounce">
            <Sparkles className="w-4 h-4 text-yellow-900" />
          </div>
        </div>

        <div>
          <h2 className="text-2xl font-display font-bold text-white mb-2">
            Creating your podcast{dots}
          </h2>
          <p className="text-augustus-400">
            Gathering the latest news and generating your personalized briefing
          </p>
        </div>

        <div className="flex justify-center gap-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="w-3 h-3 bg-accent rounded-full animate-bounce"
              style={{ animationDelay: `${i * 100}ms` }}
            />
          ))}
        </div>

        <p className="text-sm text-augustus-500">
          This usually takes 1-2 minutes. You'll be redirected to your dashboard shortly.
        </p>
      </div>
    </div>
  )
}

// ============ Main Onboarding Component ============
export default function Onboarding() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [currentStep, setCurrentStep] = useState(0)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSavingStep, setIsSavingStep] = useState(false)
  // Detect browser timezone as default
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone

  const [data, setData] = useState<OnboardingData>({
    userName: '',
    timezone: browserTimezone,
    openrouterApiKey: '',
    generalModel: '',
    writerModel: '',
    ttsProvider: 'gemini',
    geminiApiKey: '',
    elevenlabsApiKey: '',
    selectedTopics: [],
    customTopicPrompt: '',
    firstBriefingTopics: [],
  })

  // Check if already onboarded (but allow manual access to onboarding)
  useEffect(() => {
    const hasOnboarded = localStorage.getItem('augustus_onboarded')
    const wasSkipped = localStorage.getItem('augustus_onboarding_skipped')
    // Only auto-redirect if completed, not if skipped
    if (hasOnboarded === 'true' && !wasSkipped) {
      navigate('/dashboard', { replace: true })
    }
  }, [navigate])

  const updateData = (updates: Partial<OnboardingData>) => {
    setData(prev => ({ ...prev, ...updates }))
  }

  const updateWelcomeData = (updates: { userName?: string; timezone?: string }) => {
    setData(prev => ({
      ...prev,
      ...(updates.userName !== undefined && { userName: updates.userName }),
      ...(updates.timezone !== undefined && { timezone: updates.timezone }),
    }))
  }

  // Save settings incrementally after each step
  const saveWelcomeSettings = useMutation({
    mutationFn: async () => {
      const updates: Record<string, string> = {}
      if (data.userName) updates.user_name = data.userName
      if (data.timezone) updates.timezone = data.timezone
      if (Object.keys(updates).length > 0) {
        return settingsApi.update(updates)
      }
    },
  })

  const saveApiKeySettings = useMutation({
    mutationFn: async () => {
      const updates: Record<string, string> = {}
      if (data.openrouterApiKey) updates.openrouter_api_key = data.openrouterApiKey
      if (data.generalModel) updates.openrouter_model = data.generalModel
      if (data.writerModel) updates.openrouter_writer_model = data.writerModel
      if (Object.keys(updates).length > 0) {
        return settingsApi.update(updates)
      }
    },
  })

  const saveTTSSettings = useMutation({
    mutationFn: async () => {
      const updates: Record<string, string> = {}
      if (data.ttsProvider) updates.tts_provider = data.ttsProvider
      if (data.ttsProvider === 'gemini' && data.geminiApiKey) {
        updates.gemini_api_key = data.geminiApiKey
      } else if (data.ttsProvider === 'elevenlabs' && data.elevenlabsApiKey) {
        updates.elevenlabs_api_key = data.elevenlabsApiKey
      }
      if (Object.keys(updates).length > 0) {
        return settingsApi.update(updates)
      }
    },
  })

  const nextStep = async () => {
    if (currentStep < STEPS.length - 1 && !isSavingStep) {
      setIsSavingStep(true)
      try {
        // Save settings before moving to next step
        const currentStepId = STEPS[currentStep].id
        
        if (currentStepId === 'welcome') {
          // Save welcome settings (name and timezone)
          if (data.userName || data.timezone) {
            await saveWelcomeSettings.mutateAsync()
          }
        } else if (currentStepId === 'api-key') {
          // Save API key settings (so they're available for topics step)
          if (data.openrouterApiKey || data.generalModel || data.writerModel) {
            await saveApiKeySettings.mutateAsync()
            // Invalidate settings query to ensure fresh data
            queryClient.invalidateQueries({ queryKey: ['settings'] })
          }
        } else if (currentStepId === 'tts') {
          // Save TTS settings
          if (data.ttsProvider) {
            await saveTTSSettings.mutateAsync()
            queryClient.invalidateQueries({ queryKey: ['settings'] })
          }
        }
        
        setCurrentStep(prev => prev + 1)
      } catch (error) {
        console.error('Failed to save settings:', error)
        // Still allow progression even if save fails
        setCurrentStep(prev => prev + 1)
      } finally {
        setIsSavingStep(false)
      }
    }
  }

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }

  // Save settings mutation
  const saveSettingsMutation = useMutation({
    mutationFn: async () => {
      const updates: Record<string, string | boolean> = {
        user_name: data.userName,
        timezone: data.timezone,
        openrouter_api_key: data.openrouterApiKey,
        openrouter_model: data.generalModel,
        openrouter_writer_model: data.writerModel,
        tts_provider: data.ttsProvider,
      }
      if (data.ttsProvider === 'gemini' && data.geminiApiKey) {
        updates.gemini_api_key = data.geminiApiKey
      } else if (data.ttsProvider === 'elevenlabs' && data.elevenlabsApiKey) {
        updates.elevenlabs_api_key = data.elevenlabsApiKey
      }
      return settingsApi.update(updates)
    },
  })

  // Create topics mutation
  const createTopicsMutation = useMutation({
    mutationFn: async () => {
      const createdTopics: { name: string; id: string }[] = []
      for (const topic of data.selectedTopics) {
        try {
          const created = await topicsApi.create({
            name: topic.name,
            description: topic.description,
            color: topic.color,
            use_newsapi: topic.useNewsapi,
          })
          createdTopics.push({ name: topic.name, id: created.id })
        } catch (error) {
          // Topic might already exist, continue
          console.warn(`Failed to create topic ${topic.name}:`, error)
        }
      }
      
      // Handle custom topic if provided
      if (data.customTopicPrompt.trim()) {
        try {
          const generated = await topicsApi.generateFromPrompt(data.customTopicPrompt)
          const created = await topicsApi.create({
            name: generated.name,
            description: generated.description,
            use_newsapi: generated.use_newsapi,
          })
          createdTopics.push({ name: generated.name, id: created.id })
        } catch (error) {
          console.warn('Failed to create custom topic:', error)
        }
      }
      
      return createdTopics
    },
  })

  // Generate briefing mutation
  const generateMutation = useMutation({
    mutationFn: async (topicIds: string[]) => {
      return briefingsApi.generate({ topic_ids: topicIds.slice(0, 5) })
    },
  })

  // Handle skip onboarding
  const handleSkip = () => {
    // Mark onboarding as skipped
    localStorage.setItem('augustus_onboarding_skipped', 'true')
    // Navigate to dashboard
    navigate('/dashboard')
  }

  // Handle final submission
  const handleComplete = async () => {
    setIsGenerating(true)
    setCurrentStep(STEPS.length - 1) // Go to generation step

    try {
      // Save settings first
      await saveSettingsMutation.mutateAsync()
      
      // Create topics
      const createdTopics = await createTopicsMutation.mutateAsync()
      
      // Get topic IDs for first briefing
      const firstBriefingTopicIds = createdTopics
        .filter(t => data.firstBriefingTopics.includes(t.name))
        .map(t => t.id)
      
      // If no specific topics selected, use first 3
      const topicIdsToUse = firstBriefingTopicIds.length > 0 
        ? firstBriefingTopicIds 
        : createdTopics.slice(0, 3).map(t => t.id)
      
      // Generate first briefing
      if (topicIdsToUse.length > 0) {
        await generateMutation.mutateAsync(topicIdsToUse)
      }
      
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      queryClient.invalidateQueries({ queryKey: ['briefings'] })
      
      // Mark onboarding complete and clear skip flag
      localStorage.setItem('augustus_onboarded', 'true')
      localStorage.removeItem('augustus_onboarding_skipped')
      
      // Wait a moment for effect
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      // Navigate to dashboard
      navigate('/dashboard')
    } catch (error) {
      console.error('Onboarding failed:', error)
      // Still mark as onboarded so they can fix in settings
      localStorage.setItem('augustus_onboarded', 'true')
      localStorage.removeItem('augustus_onboarding_skipped')
      navigate('/dashboard')
    }
  }

  const renderStep = () => {
    switch (STEPS[currentStep].id) {
      case 'welcome':
        return (
          <WelcomeStep
            userName={data.userName}
            timezone={data.timezone}
            onUpdate={updateWelcomeData}
            onNext={nextStep}
            onSkip={handleSkip}
          />
        )
      case 'api-key':
        return (
          <ApiKeyStep
            apiKey={data.openrouterApiKey}
            generalModel={data.generalModel}
            writerModel={data.writerModel}
            onUpdate={updateData}
            onNext={nextStep}
            onBack={prevStep}
            isLoading={isSavingStep}
          />
        )
      case 'tts':
        return (
          <TTSProviderStep
            provider={data.ttsProvider}
            geminiKey={data.geminiApiKey}
            elevenlabsKey={data.elevenlabsApiKey}
            onUpdate={updateData}
            onNext={nextStep}
            onBack={prevStep}
            isLoading={isSavingStep}
          />
        )
      case 'topics':
        return (
          <TopicsStep
            selectedTopics={data.selectedTopics}
            customPrompt={data.customTopicPrompt}
            onUpdate={(topics, prompt) => updateData({ selectedTopics: topics, customTopicPrompt: prompt })}
            onNext={nextStep}
            onBack={prevStep}
          />
        )
      case 'confirm':
        return (
          <ConfirmationStep
            selectedTopics={data.selectedTopics}
            firstBriefingTopics={data.firstBriefingTopics}
            onUpdate={(topics) => updateData({ firstBriefingTopics: topics })}
            onComplete={handleComplete}
            onBack={prevStep}
            isLoading={isGenerating}
          />
        )
      case 'generate':
        return <GenerationStep />
      default:
        return null
    }
  }

  return (
    <div className="min-h-[100dvh] bg-augustus-950 flex flex-col">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-accent/5 via-transparent to-purple-500/5 pointer-events-none" />
      
      {/* Progress bar */}
      <div className="fixed top-0 left-0 right-0 h-1 bg-augustus-800 z-50">
        <div
          className="h-full bg-accent transition-all duration-500 ease-out"
          style={{ width: `${((currentStep + 1) / STEPS.length) * 100}%` }}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 pt-12 relative z-10">
        {renderStep()}
      </div>

      {/* Step indicator */}
      {currentStep < STEPS.length - 1 && (
        <div className="flex justify-center gap-2 pb-8">
          {STEPS.slice(0, -1).map((step, i) => (
            <div
              key={step.id}
              className={clsx(
                'h-2 rounded-full transition-all duration-300',
                i === currentStep ? 'bg-accent w-8' : i < currentStep ? 'bg-accent/60 w-2' : 'bg-augustus-700 w-2'
              )}
            />
          ))}
        </div>
      )}
    </div>
  )
}

