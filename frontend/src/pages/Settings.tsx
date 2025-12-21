import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Settings as SettingsIcon,
  Key,
  Cpu,
  Volume2,
  Rss,
  Save,
  Loader2,
  CheckCircle,
  AlertCircle,
  Eye,
  EyeOff,
  ExternalLink,
  Info,
  Search,
  ChevronDown,
  Clock,
  Globe,
  Mail
} from 'lucide-react'
import clsx from 'clsx'
import { settingsApi, AppSettings, ModelOption, TimezoneGroups } from '../api/client'

export default function Settings() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  // Form state
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [openrouterModel, setOpenrouterModel] = useState('')
  const [ttsProvider, setTtsProvider] = useState('piper')
  const [elevenlabsKey, setElevenlabsKey] = useState('')
  const [elevenlabsModel, setElevenlabsModel] = useState('eleven_turbo_v2_5')
  const [geminiKey, setGeminiKey] = useState('')
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash-preview-tts')
  // Duration slider values (1=Short/3min, 2=Medium/7min, 3=Long/25min)
  const [briefingDurationSlider, setBriefingDurationSlider] = useState(2)
  const [conversationComplexity, setConversationComplexity] = useState(3)
  
  // Helper functions to convert between slider values and minutes
  const durationToSlider = (minutes: number): number => {
    if (minutes <= 5) return 1 // Short (3 min)
    if (minutes <= 15) return 2 // Medium (7 min)
    return 3 // Long (25 min)
  }
  
  const sliderToDuration = (sliderValue: number): number => {
    switch (sliderValue) {
      case 1: return 3  // Short
      case 2: return 7  // Medium
      case 3: return 25 // Long
      default: return 7
    }
  }
  
  const getDurationLabel = (sliderValue: number): string => {
    switch (sliderValue) {
      case 1: return 'Short (3 min)'
      case 2: return 'Medium (7 min)'
      case 3: return 'Long (25 min)'
      default: return 'Medium (7 min)'
    }
  }
  const [timezone, setTimezone] = useState('UTC')
  const [newsApiKey, setNewsApiKey] = useState('')
  const [resendApiKey, setResendApiKey] = useState('')
  const [userName, setUserName] = useState('')
  
  // UI state
  const [showOpenrouterKey, setShowOpenrouterKey] = useState(false)
  const [showElevenlabsKey, setShowElevenlabsKey] = useState(false)
  const [showGeminiKey, setShowGeminiKey] = useState(false)
  const [showNewsApiKey, setShowNewsApiKey] = useState(false)
  const [showResendApiKey, setShowResendApiKey] = useState(false)
  const [saved, setSaved] = useState(false)
  const [modelSearch, setModelSearch] = useState('')
  const [showModelDropdown, setShowModelDropdown] = useState(false)
  const modelButtonRef = useRef<HTMLButtonElement>(null)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 })
  
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
  
  // Filter models based on search
  const filteredModels = useMemo(() => {
    if (!models) return []
    if (!modelSearch.trim()) return models
    
    const search = modelSearch.toLowerCase()
    return models.filter(model => 
      model.name.toLowerCase().includes(search) ||
      model.provider.toLowerCase().includes(search) ||
      model.id.toLowerCase().includes(search)
    )
  }, [models, modelSearch])
  
  // Group models by provider
  const groupedModels = useMemo(() => {
    const groups: Record<string, ModelOption[]> = {}
    for (const model of filteredModels) {
      if (!groups[model.provider]) {
        groups[model.provider] = []
      }
      groups[model.provider].push(model)
    }
    return groups
  }, [filteredModels])
  
  // Get selected model details
  const selectedModel = useMemo(() => {
    return models?.find(m => m.id === openrouterModel)
  }, [models, openrouterModel])
  
  // Format context length for display
  const formatContextLength = (length?: number) => {
    if (!length) return ''
    if (length >= 1000000) return `${(length / 1000000).toFixed(1)}M`
    if (length >= 1000) return `${(length / 1000).toFixed(0)}K`
    return length.toString()
  }
  
  // Handle opening the dropdown and calculating position
  const handleOpenModelDropdown = () => {
    if (modelButtonRef.current) {
      const rect = modelButtonRef.current.getBoundingClientRect()
      setDropdownPosition({
        top: rect.bottom + 8,
        left: rect.left,
        width: Math.min(rect.width, window.innerWidth - 32),
      })
    }
    setShowModelDropdown(!showModelDropdown)
  }
  
  // Update settings mutation
  const updateMutation = useMutation({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })
  
  // Initialize form with current settings
  useEffect(() => {
    if (settings) {
      setOpenrouterModel(settings.openrouter_model)
      setTtsProvider(settings.tts_provider)
      setElevenlabsModel(settings.elevenlabs_model || 'eleven_turbo_v2_5')
      setGeminiModel(settings.gemini_model || 'gemini-2.5-flash-preview-tts')
      setBriefingDurationSlider(durationToSlider(settings.briefing_duration_minutes))
      setConversationComplexity(settings.conversation_complexity || 3)
      setTimezone(settings.timezone || 'UTC')
      setUserName(settings.user_name || '')
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
    }
  }, [settings])
  
  const handleSave = () => {
    const updates: Record<string, string> = {}
    
    // Helper to check if a key is a new value (not the masked version)
    const isNewKey = (value: string, maskedValue?: string) => {
      if (!value) return false
      // If it contains "..." it's likely the masked version, don't send it
      if (value.includes('...')) return false
      // If it's the same as the masked value from settings, don't send it
      if (value === maskedValue) return false
      return true
    }
    
    // Only send API keys if they're new (not masked values)
    if (isNewKey(openrouterKey, settings?.openrouter_api_key)) {
      updates.openrouter_api_key = openrouterKey
    }
    if (isNewKey(elevenlabsKey, settings?.elevenlabs_api_key)) {
      updates.elevenlabs_api_key = elevenlabsKey
    }
    if (isNewKey(geminiKey, settings?.gemini_api_key)) {
      updates.gemini_api_key = geminiKey
    }
    if (isNewKey(newsApiKey, settings?.news_api_key)) {
      updates.news_api_key = newsApiKey
    }
    if (isNewKey(resendApiKey, settings?.resend_api_key)) {
      updates.resend_api_key = resendApiKey
    }
    
    // Always send non-key settings if changed
    if (openrouterModel !== settings?.openrouter_model) updates.openrouter_model = openrouterModel
    if (ttsProvider !== settings?.tts_provider) updates.tts_provider = ttsProvider
    if (elevenlabsModel !== settings?.elevenlabs_model) updates.elevenlabs_model = elevenlabsModel
    if (geminiModel !== settings?.gemini_model) updates.gemini_model = geminiModel
    const briefingDuration = sliderToDuration(briefingDurationSlider)
    
    if (briefingDuration !== settings?.briefing_duration_minutes) updates.briefing_duration_minutes = briefingDuration
    if (conversationComplexity !== settings?.conversation_complexity) updates.conversation_complexity = conversationComplexity
    if (timezone !== settings?.timezone) updates.timezone = timezone
    if (userName !== settings?.user_name) updates.user_name = userName
    
    if (Object.keys(updates).length > 0) {
      updateMutation.mutate(updates)
    }
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
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          Settings
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Configure API keys and integrations for Augustus
        </p>
      </div>
      
      {/* Success message */}
      {saved && (
        <div className="mb-4 sm:mb-6 p-3 sm:p-4 bg-green-500/10 border border-green-500/20 rounded-lg flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
          <span className="text-green-400 text-sm sm:text-base">Settings saved successfully!</span>
        </div>
      )}
      
      {/* OpenRouter Section */}
      <div className="card mb-4 sm:mb-6 overflow-visible">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2 flex-wrap">
          <Cpu className="w-5 h-5 text-accent flex-shrink-0" />
          <span>LLM Provider (OpenRouter)</span>
          {settings?.openrouter_configured ? (
            <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">
              Configured
            </span>
          ) : (
            <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
              Not configured
            </span>
          )}
        </h2>
        
        <p className="text-xs sm:text-sm text-augustus-400 mb-3 sm:mb-4">
          OpenRouter provides access to multiple AI models.{' '}
          <a 
            href="https://openrouter.ai/keys" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-accent hover:underline inline-flex items-center gap-1"
          >
            Get an API key <ExternalLink className="w-3 h-3" />
          </a>
        </p>
        
        <div className="space-y-4">
          <div>
            <label className="label">API Key</label>
            <div className="relative">
              <Key className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 sm:w-5 h-4 sm:h-5 text-augustus-500" />
              <input
                type={showOpenrouterKey ? 'text' : 'password'}
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
                placeholder={settings?.openrouter_api_key || 'sk-or-...'}
                className="input pl-10 sm:pl-12 pr-10 sm:pr-12"
              />
              <button
                type="button"
                onClick={() => setShowOpenrouterKey(!showOpenrouterKey)}
                className="absolute right-3 sm:right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300 p-1"
              >
                {showOpenrouterKey ? <EyeOff className="w-4 sm:w-5 h-4 sm:h-5" /> : <Eye className="w-4 sm:w-5 h-4 sm:h-5" />}
              </button>
            </div>
          </div>
          
          <div>
            <label className="label">Model</label>
            
            {/* Selected model display / dropdown trigger */}
            <button
              ref={modelButtonRef}
              type="button"
              onClick={handleOpenModelDropdown}
              className="input w-full text-left flex items-center justify-between"
            >
              <div className="flex-1 min-w-0">
                {selectedModel ? (
                  <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                    <span className="text-white text-sm sm:text-base truncate">{selectedModel.name}</span>
                    <span className="text-augustus-500 text-xs sm:text-sm hidden sm:inline">({selectedModel.provider})</span>
                  </div>
                ) : (
                  <span className="text-augustus-500 text-sm sm:text-base">Select a model...</span>
                )}
              </div>
              <ChevronDown className={clsx(
                'w-5 h-5 text-augustus-500 transition-transform flex-shrink-0',
                showModelDropdown && 'rotate-180'
              )} />
            </button>
          </div>
        </div>
      </div>
      
      {/* TTS Section */}
      <div className="card mb-4 sm:mb-6">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Volume2 className="w-5 h-5 text-accent" />
          Text-to-Speech Provider
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="label">Provider</label>
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
              <button
                type="button"
                onClick={() => setTtsProvider('piper')}
                className={clsx(
                  'flex-1 p-3 sm:p-4 rounded-lg border-2 transition-all text-left',
                  ttsProvider === 'piper'
                    ? 'border-accent bg-accent/10'
                    : 'border-augustus-700 hover:border-augustus-600 active:bg-augustus-800'
                )}
              >
                <div className="font-medium text-white text-sm sm:text-base">Piper</div>
                <div className="text-xs sm:text-sm text-augustus-400">
                  Self-hosted, free, good quality
                </div>
              </button>
              
              <button
                type="button"
                onClick={() => setTtsProvider('elevenlabs')}
                className={clsx(
                  'flex-1 p-3 sm:p-4 rounded-lg border-2 transition-all text-left',
                  ttsProvider === 'elevenlabs'
                    ? 'border-accent bg-accent/10'
                    : 'border-augustus-700 hover:border-augustus-600 active:bg-augustus-800'
                )}
              >
                <div className="font-medium text-white flex items-center gap-2 text-sm sm:text-base">
                  ElevenLabs
                  {settings?.elevenlabs_configured && (
                    <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                      Ready
                    </span>
                  )}
                </div>
                <div className="text-xs sm:text-sm text-augustus-400">
                  Cloud API, premium quality
                </div>
              </button>

              <button
                type="button"
                onClick={() => setTtsProvider('gemini')}
                className={clsx(
                  'flex-1 p-3 sm:p-4 rounded-lg border-2 transition-all text-left',
                  ttsProvider === 'gemini'
                    ? 'border-accent bg-accent/10'
                    : 'border-augustus-700 hover:border-augustus-600 active:bg-augustus-800'
                )}
              >
                <div className="font-medium text-white flex items-center gap-2 text-sm sm:text-base">
                  Google Gemini
                  {settings?.gemini_configured && (
                    <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                      Ready
                    </span>
                  )}
                </div>
                <div className="text-xs sm:text-sm text-augustus-400">
                  Native TTS, expressiveness
                </div>
              </button>
            </div>
          </div>
          
          {ttsProvider === 'elevenlabs' && (
            <>
              <div>
                <label className="label">
                  ElevenLabs API Key
                </label>
                <div className="relative">
                  <Key className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 sm:w-5 h-4 sm:h-5 text-augustus-500" />
                  <input
                    type={showElevenlabsKey ? 'text' : 'password'}
                    value={elevenlabsKey}
                    onChange={(e) => setElevenlabsKey(e.target.value)}
                    placeholder={settings?.elevenlabs_api_key || 'Enter ElevenLabs API key'}
                    className="input pl-10 sm:pl-12 pr-10 sm:pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowElevenlabsKey(!showElevenlabsKey)}
                    className="absolute right-3 sm:right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300 p-1"
                  >
                    {showElevenlabsKey ? <EyeOff className="w-4 sm:w-5 h-4 sm:h-5" /> : <Eye className="w-4 sm:w-5 h-4 sm:h-5" />}
                  </button>
                </div>
              </div>
              
              <div>
                <label className="label">TTS Model</label>
                <input
                  type="text"
                  value={elevenlabsModel}
                  onChange={(e) => setElevenlabsModel(e.target.value)}
                  placeholder="eleven_turbo_v2_5"
                  className="input"
                />
                <p className="text-xs text-augustus-500 mt-1">
                  Default: eleven_turbo_v2_5 (fastest)
                </p>
              </div>
            </>
          )}

          {ttsProvider === 'gemini' && (
            <>
              <div>
                <label className="label">
                  Gemini API Key
                </label>
                <div className="relative">
                  <Key className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 sm:w-5 h-4 sm:h-5 text-augustus-500" />
                  <input
                    type={showGeminiKey ? 'text' : 'password'}
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    placeholder={settings?.gemini_api_key || 'Enter Gemini API key'}
                    className="input pl-10 sm:pl-12 pr-10 sm:pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowGeminiKey(!showGeminiKey)}
                    className="absolute right-3 sm:right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300 p-1"
                  >
                    {showGeminiKey ? <EyeOff className="w-4 sm:w-5 h-4 sm:h-5" /> : <Eye className="w-4 sm:w-5 h-4 sm:h-5" />}
                  </button>
                </div>
                <p className="text-xs text-augustus-500 mt-1">
                  Gemini TTS is currently in preview and requires a Gemini 2.0+ API key.
                </p>
              </div>

              <div>
                <label className="label">TTS Model</label>
                <input
                  type="text"
                  value={geminiModel}
                  onChange={(e) => setGeminiModel(e.target.value)}
                  placeholder="gemini-2.5-flash-preview-tts"
                  className="input"
                />
                <p className="text-xs text-augustus-500 mt-1">
                  Default: gemini-2.5-flash-preview-tts
                </p>
              </div>
            </>
          )}
          
          {/* Duration Configuration */}
          <div className="pt-4 border-t border-augustus-700">
            <h3 className="text-sm font-medium text-white mb-2 sm:mb-3">Content Duration</h3>
            <p className="text-xs text-augustus-400 mb-3 sm:mb-4">
              Target duration for audio content
            </p>
            
            <div>
              {/* Daily Briefing Duration */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="label text-xs sm:text-sm mb-0">Daily Briefing</label>
                  <span className="text-xs sm:text-sm font-medium text-white">
                    {getDurationLabel(briefingDurationSlider)}
                  </span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={3}
                  step={1}
                  value={briefingDurationSlider}
                  onChange={(e) => setBriefingDurationSlider(parseInt(e.target.value))}
                  className="w-full h-2 bg-augustus-700 rounded-lg appearance-none cursor-pointer accent-accent"
                />
                <div className="flex justify-between mt-1 px-1">
                  <span className="text-xs text-augustus-500">Short</span>
                  <span className="text-xs text-augustus-500">Medium</span>
                  <span className="text-xs text-augustus-500">Long</span>
                </div>
                <div className="flex justify-between mt-1 px-1">
                  {[1, 2, 3].map((level) => (
                    <div
                      key={level}
                      className={clsx(
                        'w-2 h-2 rounded-full transition-colors',
                        level <= briefingDurationSlider ? 'bg-accent' : 'bg-augustus-600'
                      )}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
          
          {/* Conversation Complexity */}
          <div className="pt-4 border-t border-augustus-700">
            <h3 className="text-sm font-medium text-white mb-2 sm:mb-3">Language & Complexity</h3>
            
            <div className="space-y-4">
              {/* Complexity Slider */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs text-augustus-400">Casual</span>
                  <span className="text-xs sm:text-sm font-medium text-white">
                    {conversationComplexity === 1 && 'Casual'}
                    {conversationComplexity === 2 && 'Accessible'}
                    {conversationComplexity === 3 && 'Standard'}
                    {conversationComplexity === 4 && 'Advanced'}
                    {conversationComplexity === 5 && 'Expert'}
                  </span>
                  <span className="text-xs text-augustus-400">Expert</span>
                </div>
                
                <input
                  type="range"
                  min={1}
                  max={5}
                  step={1}
                  value={conversationComplexity}
                  onChange={(e) => setConversationComplexity(parseInt(e.target.value))}
                  className="w-full h-2 bg-augustus-700 rounded-lg appearance-none cursor-pointer accent-accent"
                />
                
                {/* Level markers */}
                <div className="flex justify-between mt-1 px-1">
                  {[1, 2, 3, 4, 5].map((level) => (
                    <div
                      key={level}
                      className={clsx(
                        'w-2 h-2 rounded-full transition-colors',
                        level <= conversationComplexity ? 'bg-accent' : 'bg-augustus-600'
                      )}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Personalization Section */}
      <div className="card mb-4 sm:mb-6">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-accent" />
          Personalization
        </h2>
        
        <div>
          <label className="label">Your Name</label>
          <input
            type="text"
            value={userName}
            onChange={(e) => setUserName(e.target.value)}
            placeholder="Enter your name (e.g., David)"
            className="input"
          />
          <p className="text-xs text-augustus-500 mt-2">
            Hosts will address you by name in podcasts
          </p>
        </div>
      </div>
      
      {/* Timezone Section */}
      <div className="card mb-4 sm:mb-6">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5 text-accent" />
          Timezone
        </h2>
        
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
      
      {/* News Sources Section */}
      <div className="card mb-4 sm:mb-6">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Rss className="w-5 h-5 text-accent" />
          News Sources
        </h2>
        
        <div>
          <label className="label">NewsAPI Key (optional)</label>
          <div className="relative">
            <Key className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 sm:w-5 h-4 sm:h-5 text-augustus-500" />
            <input
              type={showNewsApiKey ? 'text' : 'password'}
              value={newsApiKey}
              onChange={(e) => setNewsApiKey(e.target.value)}
              placeholder={settings?.news_api_key || 'Enter NewsAPI key'}
              className="input pl-10 sm:pl-12 pr-10 sm:pr-12"
            />
            <button
              type="button"
              onClick={() => setShowNewsApiKey(!showNewsApiKey)}
              className="absolute right-3 sm:right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300 p-1"
            >
              {showNewsApiKey ? <EyeOff className="w-4 sm:w-5 h-4 sm:h-5" /> : <Eye className="w-4 sm:w-5 h-4 sm:h-5" />}
            </button>
          </div>
        </div>
      </div>
      
      {/* Email Notifications Section */}
      <div className="card mb-4 sm:mb-6">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2 flex-wrap">
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
        </h2>
        
        <div>
          <label className="label">Resend API Key</label>
          <div className="relative">
            <Key className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-4 sm:w-5 h-4 sm:h-5 text-augustus-500" />
            <input
              type={showResendApiKey ? 'text' : 'password'}
              value={resendApiKey}
              onChange={(e) => setResendApiKey(e.target.value)}
              placeholder={settings?.resend_api_key || 're_xxxxxxxxxxxxxxxxxxxxx'}
              className="input pl-10 sm:pl-12 pr-10 sm:pr-12"
            />
            <button
              type="button"
              onClick={() => setShowResendApiKey(!showResendApiKey)}
              className="absolute right-3 sm:right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300 p-1"
            >
              {showResendApiKey ? <EyeOff className="w-4 sm:w-5 h-4 sm:h-5" /> : <Eye className="w-4 sm:w-5 h-4 sm:h-5" />}
            </button>
          </div>
        </div>
      </div>
      
      {/* Save Button - Sticky on mobile */}
      <div className="sticky bottom-0 py-4 bg-gradient-to-t from-augustus-950 via-augustus-950 to-transparent -mx-4 px-4 sm:static sm:py-0 sm:bg-transparent sm:mx-0 sm:px-0">
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="btn btn-primary flex items-center gap-2 w-full sm:w-auto"
          >
            {updateMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                Save Settings
              </>
            )}
          </button>
        </div>
      </div>
      
      {/* About Button */}
      <div className="mt-6 sm:mt-8">
        <button
          onClick={() => navigate('/about')}
          className="w-full card hover:border-augustus-600 transition-colors cursor-pointer group active:scale-[0.99] flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <Info className="w-5 h-5 text-accent flex-shrink-0" />
            <div className="text-left">
              <h3 className="text-base sm:text-lg font-semibold text-white group-hover:text-accent transition-colors">
                About Augustus
              </h3>
              <p className="text-xs sm:text-sm text-augustus-400 mt-0.5">
                Learn more about the app, server, and creator
              </p>
            </div>
          </div>
          <ExternalLink className="w-5 h-5 text-augustus-600 group-hover:text-augustus-400 transition-colors flex-shrink-0" />
        </button>
      </div>
      
      {/* Model Dropdown - Fixed position portal */}
      {showModelDropdown && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-[9998]" 
            onClick={() => {
              setShowModelDropdown(false)
              setModelSearch('')
            }}
          />
          
          {/* Dropdown - On mobile, show as bottom sheet */}
          <div 
            className={clsx(
              "fixed z-[9999] bg-augustus-900 border border-augustus-700 shadow-2xl overflow-hidden",
              // Mobile: bottom sheet style
              "inset-x-0 bottom-0 rounded-t-2xl max-h-[70vh]",
              // Desktop: dropdown style
              "sm:inset-auto sm:rounded-lg sm:max-h-96"
            )}
            style={{
              ...(window.innerWidth >= 640 && {
                top: dropdownPosition.top,
                left: dropdownPosition.left,
                width: dropdownPosition.width,
              }),
            }}
          >
            {/* Mobile handle */}
            <div className="sm:hidden w-10 h-1 bg-augustus-600 rounded-full mx-auto mt-3 mb-2" />
            
            {/* Search input */}
            <div className="p-2 sm:p-2 border-b border-augustus-700">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-augustus-500" />
                <input
                  type="text"
                  value={modelSearch}
                  onChange={(e) => setModelSearch(e.target.value)}
                  placeholder="Search models..."
                  className="w-full pl-9 pr-4 py-2.5 sm:py-2 bg-augustus-800 border border-augustus-700 rounded-lg text-white text-sm placeholder-augustus-500 focus:outline-none focus:border-accent"
                  autoFocus
                />
              </div>
            </div>
            
            {/* Models list */}
            <div className="overflow-y-auto max-h-[50vh] sm:max-h-72">
              {modelsLoading ? (
                <div className="p-4 text-center">
                  <Loader2 className="w-5 h-5 animate-spin text-accent mx-auto" />
                  <p className="text-sm text-augustus-500 mt-2">Loading models...</p>
                </div>
              ) : Object.keys(groupedModels).length === 0 ? (
                <div className="p-4 text-center text-augustus-500 text-sm">
                  No models found
                </div>
              ) : (
                Object.entries(groupedModels).map(([provider, providerModels]) => (
                  <div key={provider}>
                    <div className="px-3 py-2 bg-augustus-800/50 text-xs font-semibold text-augustus-400 uppercase tracking-wide sticky top-0">
                      {provider}
                    </div>
                    {providerModels.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        onClick={() => {
                          setOpenrouterModel(model.id)
                          setShowModelDropdown(false)
                          setModelSearch('')
                        }}
                        className={clsx(
                          'w-full px-3 py-3 sm:py-2 text-left hover:bg-augustus-800 active:bg-augustus-700 transition-colors flex items-center justify-between',
                          model.id === openrouterModel && 'bg-accent/10 border-l-2 border-accent'
                        )}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="text-white text-sm truncate">{model.name}</div>
                          <div className="text-augustus-500 text-xs truncate">{model.id}</div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                          {model.context_length && (
                            <span className="px-1.5 py-0.5 bg-augustus-700 text-augustus-400 text-xs rounded">
                              {formatContextLength(model.context_length)}
                            </span>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
            
            {/* Model count */}
            <div className="p-2 border-t border-augustus-700 text-xs text-augustus-500 text-center pb-safe">
              {filteredModels.length} model{filteredModels.length !== 1 ? 's' : ''} available
            </div>
          </div>
        </>
      )}
    </div>
  )
}
