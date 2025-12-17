import { useState, useEffect, useMemo, useRef } from 'react'
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
  Globe
} from 'lucide-react'
import clsx from 'clsx'
import { settingsApi, AppSettings, ModelOption, TimezoneGroups } from '../api/client'

export default function Settings() {
  const queryClient = useQueryClient()
  
  // Form state
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [openrouterModel, setOpenrouterModel] = useState('')
  const [ttsProvider, setTtsProvider] = useState('piper')
  const [elevenlabsKey, setElevenlabsKey] = useState('')
  const [elevenlabsModel, setElevenlabsModel] = useState('eleven_turbo_v2_5')
  const [voiceHost1, setVoiceHost1] = useState('21m00Tcm4TlvDq8ikWAM')
  const [voiceHost2, setVoiceHost2] = useState('AZnzlk1XvdvUeBnXmlld')
  const [briefingDuration, setBriefingDuration] = useState(5)
  const [deepcastDuration, setDeepcastDuration] = useState(10)
  const [stationUpdateDuration, setStationUpdateDuration] = useState(3)
  const [conversationComplexity, setConversationComplexity] = useState(3)
  const [timezone, setTimezone] = useState('UTC')
  const [newsApiKey, setNewsApiKey] = useState('')
  const [userName, setUserName] = useState('')
  
  // UI state
  const [showOpenrouterKey, setShowOpenrouterKey] = useState(false)
  const [showElevenlabsKey, setShowElevenlabsKey] = useState(false)
  const [showNewsApiKey, setShowNewsApiKey] = useState(false)
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
        width: rect.width,
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
      setVoiceHost1(settings.tts_voice_host1)
      setVoiceHost2(settings.tts_voice_host2)
      setBriefingDuration(settings.briefing_duration_minutes)
      setDeepcastDuration(settings.deepcast_duration_minutes)
      setStationUpdateDuration(settings.station_update_duration_minutes)
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
      if (!newsApiKey && settings.news_api_key) {
        setNewsApiKey(settings.news_api_key)
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
    if (isNewKey(newsApiKey, settings?.news_api_key)) {
      updates.news_api_key = newsApiKey
    }
    
    // Always send non-key settings if changed
    if (openrouterModel !== settings?.openrouter_model) updates.openrouter_model = openrouterModel
    if (ttsProvider !== settings?.tts_provider) updates.tts_provider = ttsProvider
    if (elevenlabsModel !== settings?.elevenlabs_model) updates.elevenlabs_model = elevenlabsModel
    if (voiceHost1 !== settings?.tts_voice_host1) updates.tts_voice_host1 = voiceHost1
    if (voiceHost2 !== settings?.tts_voice_host2) updates.tts_voice_host2 = voiceHost2
    if (briefingDuration !== settings?.briefing_duration_minutes) updates.briefing_duration_minutes = briefingDuration
    if (deepcastDuration !== settings?.deepcast_duration_minutes) updates.deepcast_duration_minutes = deepcastDuration
    if (stationUpdateDuration !== settings?.station_update_duration_minutes) updates.station_update_duration_minutes = stationUpdateDuration
    if (conversationComplexity !== settings?.conversation_complexity) updates.conversation_complexity = conversationComplexity
    if (timezone !== settings?.timezone) updates.timezone = timezone
    if (userName !== settings?.user_name) updates.user_name = userName
    
    if (Object.keys(updates).length > 0) {
      updateMutation.mutate(updates)
    }
  }
  
  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="p-8">
        <div className="card text-center py-12">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-augustus-400">Failed to load settings. Is the backend running?</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="p-8 max-w-3xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-semibold text-white mb-2">
          Settings
        </h1>
        <p className="text-augustus-400">
          Configure API keys and integrations for Augustus
        </p>
      </div>
      
      {/* Success message */}
      {saved && (
        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/20 rounded-lg flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-400" />
          <span className="text-green-400">Settings saved successfully!</span>
        </div>
      )}
      
      {/* OpenRouter Section */}
      <div className="card mb-6 overflow-visible">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-accent" />
          LLM Provider (OpenRouter)
          {settings?.openrouter_configured ? (
            <span className="ml-auto px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">
              Configured
            </span>
          ) : (
            <span className="ml-auto px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
              Not configured
            </span>
          )}
        </h2>
        
        <p className="text-sm text-augustus-400 mb-4">
          OpenRouter provides access to multiple AI models through a single API.{' '}
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
              <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-augustus-500" />
              <input
                type={showOpenrouterKey ? 'text' : 'password'}
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
                placeholder={settings?.openrouter_api_key || 'sk-or-...'}
                className="input pl-12 pr-12"
              />
              <button
                type="button"
                onClick={() => setShowOpenrouterKey(!showOpenrouterKey)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300"
              >
                {showOpenrouterKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
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
                  <div className="flex items-center gap-2">
                    <span className="text-white truncate">{selectedModel.name}</span>
                    <span className="text-augustus-500 text-sm">({selectedModel.provider})</span>
                    {selectedModel.context_length && (
                      <span className="px-1.5 py-0.5 bg-augustus-700 text-augustus-400 text-xs rounded">
                        {formatContextLength(selectedModel.context_length)} ctx
                      </span>
                    )}
                  </div>
                ) : (
                  <span className="text-augustus-500">Select a model...</span>
                )}
              </div>
              <ChevronDown className={clsx(
                'w-5 h-5 text-augustus-500 transition-transform',
                showModelDropdown && 'rotate-180'
              )} />
            </button>
          </div>
        </div>
      </div>
      
      {/* TTS Section */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Volume2 className="w-5 h-5 text-accent" />
          Text-to-Speech Provider
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="label">Provider</label>
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => setTtsProvider('piper')}
                className={clsx(
                  'flex-1 p-4 rounded-lg border-2 transition-all text-left',
                  ttsProvider === 'piper'
                    ? 'border-accent bg-accent/10'
                    : 'border-augustus-700 hover:border-augustus-600'
                )}
              >
                <div className="font-medium text-white">Piper</div>
                <div className="text-sm text-augustus-400">
                  Self-hosted, free, good quality
                </div>
              </button>
              
              <button
                type="button"
                onClick={() => setTtsProvider('elevenlabs')}
                className={clsx(
                  'flex-1 p-4 rounded-lg border-2 transition-all text-left',
                  ttsProvider === 'elevenlabs'
                    ? 'border-accent bg-accent/10'
                    : 'border-augustus-700 hover:border-augustus-600'
                )}
              >
                <div className="font-medium text-white flex items-center gap-2">
                  ElevenLabs
                  {settings?.elevenlabs_configured && (
                    <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                      Ready
                    </span>
                  )}
                </div>
                <div className="text-sm text-augustus-400">
                  Cloud API, premium quality
                </div>
              </button>
            </div>
          </div>
          
          {ttsProvider === 'elevenlabs' && (
            <>
              <div>
                <label className="label">
                  ElevenLabs API Key{' '}
                  <a 
                    href="https://elevenlabs.io/app/settings/api-keys" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-accent hover:underline inline-flex items-center gap-1 font-normal"
                  >
                    Get key <ExternalLink className="w-3 h-3" />
                  </a>
                </label>
                <div className="relative">
                  <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-augustus-500" />
                  <input
                    type={showElevenlabsKey ? 'text' : 'password'}
                    value={elevenlabsKey}
                    onChange={(e) => setElevenlabsKey(e.target.value)}
                    placeholder={settings?.elevenlabs_api_key || 'Enter ElevenLabs API key'}
                    className="input pl-12 pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowElevenlabsKey(!showElevenlabsKey)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300"
                  >
                    {showElevenlabsKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
              
              <div>
                <label className="label">
                  TTS Model{' '}
                  <a 
                    href="https://elevenlabs.io/docs/api-reference/text-to-speech" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-accent hover:underline inline-flex items-center gap-1 font-normal"
                  >
                    View models <ExternalLink className="w-3 h-3" />
                  </a>
                </label>
                <input
                  type="text"
                  value={elevenlabsModel}
                  onChange={(e) => setElevenlabsModel(e.target.value)}
                  placeholder="eleven_turbo_v2_5"
                  className="input"
                />
                <p className="text-xs text-augustus-500 mt-1">
                  Default: eleven_turbo_v2_5 (fastest). Other options: eleven_multilingual_v2, eleven_monolingual_v1
                </p>
              </div>
            </>
          )}
          
          {/* Voice Configuration */}
          <div className="pt-4 border-t border-augustus-700">
            <h3 className="text-sm font-medium text-white mb-3">Voice Configuration</h3>
            <p className="text-xs text-augustus-400 mb-4">
              {ttsProvider === 'elevenlabs' 
                ? 'Enter ElevenLabs voice IDs. Find voices at elevenlabs.io/voice-library'
                : 'Enter Piper voice names like "en_US-lessac-medium"'}
            </p>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Host 1 Voice (Alex)</label>
                <input
                  type="text"
                  value={voiceHost1}
                  onChange={(e) => setVoiceHost1(e.target.value)}
                  placeholder={ttsProvider === 'elevenlabs' ? '21m00Tcm4TlvDq8ikWAM' : 'en_US-lessac-medium'}
                  className="input"
                />
                {ttsProvider === 'elevenlabs' && (
                  <p className="text-xs text-augustus-500 mt-1">Default: Rachel (21m00Tcm4TlvDq8ikWAM)</p>
                )}
              </div>
              
              <div>
                <label className="label">Host 2 Voice (Sam)</label>
                <input
                  type="text"
                  value={voiceHost2}
                  onChange={(e) => setVoiceHost2(e.target.value)}
                  placeholder={ttsProvider === 'elevenlabs' ? 'AZnzlk1XvdvUeBnXmlld' : 'en_US-amy-medium'}
                  className="input"
                />
                {ttsProvider === 'elevenlabs' && (
                  <p className="text-xs text-augustus-500 mt-1">Default: Domi (AZnzlk1XvdvUeBnXmlld)</p>
                )}
              </div>
            </div>
            
            {ttsProvider === 'elevenlabs' && (
              <div className="mt-3 p-3 bg-augustus-800/50 rounded-lg">
                <p className="text-xs text-augustus-400">
                  <strong className="text-white">Popular ElevenLabs voices:</strong><br />
                  • Rachel (21m00Tcm4TlvDq8ikWAM) - Calm female<br />
                  • Domi (AZnzlk1XvdvUeBnXmlld) - Strong female<br />
                  • Adam (pNInz6obpgDQGcFmaJgB) - Deep male<br />
                  • Josh (TxGEqnHWrfWFTfGW9XjX) - Young male<br />
                  • Antoni (ErXwobaYiN019PkySvjV) - Well-rounded male<br />
                  • Bella (EXAVITQu4vr4xnSDxMaL) - Soft female
                </p>
              </div>
            )}
          </div>
          
          {/* Duration Configuration */}
          <div className="pt-4 border-t border-augustus-700">
            <h3 className="text-sm font-medium text-white mb-3">Content Duration</h3>
            <p className="text-xs text-augustus-400 mb-4">
              Set the target duration for each type of audio content (in minutes)
            </p>
            
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="label">Daily Briefing</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={briefingDuration}
                    onChange={(e) => setBriefingDuration(Math.max(1, Math.min(30, parseInt(e.target.value) || 5)))}
                    className="input text-center"
                  />
                  <span className="text-augustus-400 text-sm">min</span>
                </div>
                <p className="text-xs text-augustus-500 mt-1">Quick news updates</p>
              </div>
              
              <div>
                <label className="label">DeepCast</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={5}
                    max={60}
                    value={deepcastDuration}
                    onChange={(e) => setDeepcastDuration(Math.max(5, Math.min(60, parseInt(e.target.value) || 10)))}
                    className="input text-center"
                  />
                  <span className="text-augustus-400 text-sm">min</span>
                </div>
                <p className="text-xs text-augustus-500 mt-1">In-depth research</p>
              </div>
              
              <div>
                <label className="label">Station Update</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    max={15}
                    value={stationUpdateDuration}
                    onChange={(e) => setStationUpdateDuration(Math.max(1, Math.min(15, parseInt(e.target.value) || 3)))}
                    className="input text-center"
                  />
                  <span className="text-augustus-400 text-sm">min</span>
                </div>
                <p className="text-xs text-augustus-500 mt-1">Topic updates</p>
              </div>
            </div>
          </div>
          
          {/* Conversation Complexity */}
          <div className="pt-4 border-t border-augustus-700">
            <h3 className="text-sm font-medium text-white mb-3">Language & Complexity</h3>
            <p className="text-xs text-augustus-400 mb-4">
              Adjust the language level and depth of discussion in generated podcasts
            </p>
            
            <div className="space-y-4">
              {/* Complexity Slider */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs text-augustus-400">Casual</span>
                  <span className="text-sm font-medium text-white">
                    {conversationComplexity === 1 && 'Casual (High School)'}
                    {conversationComplexity === 2 && 'Accessible (General)'}
                    {conversationComplexity === 3 && 'Standard (College)'}
                    {conversationComplexity === 4 && 'Advanced (Graduate)'}
                    {conversationComplexity === 5 && 'Expert (PhD)'}
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
              
              {/* Description for current level */}
              <div className="p-3 bg-augustus-800/50 rounded-lg">
                <p className="text-xs text-augustus-400">
                  {conversationComplexity === 1 && (
                    <>
                      <strong className="text-white">Casual:</strong> Simple, everyday language. 
                      No jargon or technical terms. Like explaining things to a smart teenager. 
                      Great for casual listening or when you want the basics.
                    </>
                  )}
                  {conversationComplexity === 2 && (
                    <>
                      <strong className="text-white">Accessible:</strong> Clear, straightforward language. 
                      Technical terms are explained when used. Good for general audiences who want 
                      to understand topics without specialized knowledge.
                    </>
                  )}
                  {conversationComplexity === 3 && (
                    <>
                      <strong className="text-white">Standard:</strong> Balanced depth and accessibility. 
                      Assumes basic familiarity with topics. Like an informed discussion between 
                      knowledgeable friends. The default setting.
                    </>
                  )}
                  {conversationComplexity === 4 && (
                    <>
                      <strong className="text-white">Advanced:</strong> Technical language and deeper analysis. 
                      Assumes background knowledge. References frameworks and theories. 
                      For professionals or enthusiasts who want more depth.
                    </>
                  )}
                  {conversationComplexity === 5 && (
                    <>
                      <strong className="text-white">Expert:</strong> Specialized terminology and academic depth. 
                      Assumes expert-level knowledge. Explores nuances, edge cases, and research. 
                      For specialists who want maximum depth.
                    </>
                  )}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Personalization Section */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-accent" />
          Personalization
        </h2>
        
        <p className="text-sm text-augustus-400 mb-4">
          Customize your podcast experience with personalized introductions.
        </p>
        
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
            Hosts will address you by name in podcast introductions (e.g., "Hey David, let's kick off today's briefing")
          </p>
        </div>
      </div>
      
      {/* Timezone Section */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5 text-accent" />
          Timezone
        </h2>
        
        <p className="text-sm text-augustus-400 mb-4">
          Set your local timezone for accurate scheduling and date display throughout the app.
        </p>
        
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
          <p className="text-xs text-augustus-500 mt-2">
            Current selection: <span className="text-augustus-300">{timezone}</span>
          </p>
        </div>
      </div>
      
      {/* News Sources Section */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Rss className="w-5 h-5 text-accent" />
          News Sources
        </h2>
        
        <div className="space-y-4">
          <div>
            <label className="label">
              NewsAPI Key (optional){' '}
              <a 
                href="https://newsapi.org/register" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-accent hover:underline inline-flex items-center gap-1 font-normal"
              >
                Get free key <ExternalLink className="w-3 h-3" />
              </a>
            </label>
            <div className="relative">
              <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-augustus-500" />
              <input
                type={showNewsApiKey ? 'text' : 'password'}
                value={newsApiKey}
                onChange={(e) => setNewsApiKey(e.target.value)}
                placeholder={settings?.news_api_key || 'Enter NewsAPI key (optional)'}
                className="input pl-12 pr-12"
              />
              <button
                type="button"
                onClick={() => setShowNewsApiKey(!showNewsApiKey)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-augustus-500 hover:text-augustus-300"
              >
                {showNewsApiKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
            <p className="text-xs text-augustus-500 mt-1">
              Enables additional news sources for briefings
            </p>
          </div>
        </div>
      </div>
      
      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="btn btn-primary flex items-center gap-2"
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
      
      {/* Info Section */}
      <div className="card mt-8 bg-augustus-900/30">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Info className="w-5 h-5 text-accent" />
          About Augustus
        </h2>
        
        <div className="space-y-3 text-sm text-augustus-400">
          <p>
            <strong className="text-white">Augustus</strong> (OpenHuxe) is a self-hosted 
            audio intelligence platform that transforms content into AI-generated podcasts.
          </p>
          
          <div className="flex items-center gap-4 pt-2 border-t border-augustus-800/50">
            <span>Version 0.1.0</span>
            <span>•</span>
            <a 
              href="https://github.com/openhuxe/augustus" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              GitHub
            </a>
            <span>•</span>
            <a 
              href="https://openrouter.ai" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              OpenRouter
            </a>
          </div>
        </div>
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
          
          {/* Dropdown */}
          <div 
            className="fixed z-[9999] bg-augustus-900 border border-augustus-700 rounded-lg shadow-2xl max-h-96 overflow-hidden"
            style={{
              top: dropdownPosition.top,
              left: dropdownPosition.left,
              width: dropdownPosition.width,
            }}
          >
            {/* Search input */}
            <div className="p-2 border-b border-augustus-700">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-augustus-500" />
                <input
                  type="text"
                  value={modelSearch}
                  onChange={(e) => setModelSearch(e.target.value)}
                  placeholder="Search models..."
                  className="w-full pl-9 pr-4 py-2 bg-augustus-800 border border-augustus-700 rounded-lg text-white text-sm placeholder-augustus-500 focus:outline-none focus:border-accent"
                  autoFocus
                />
              </div>
            </div>
            
            {/* Models list */}
            <div className="overflow-y-auto max-h-72">
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
                          'w-full px-3 py-2 text-left hover:bg-augustus-800 transition-colors flex items-center justify-between',
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
                          {model.pricing && model.pricing.prompt > 0 && (
                            <span className="px-1.5 py-0.5 bg-augustus-700 text-augustus-400 text-xs rounded">
                              ${model.pricing.prompt.toFixed(2)}/M
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
            <div className="p-2 border-t border-augustus-700 text-xs text-augustus-500 text-center">
              {filteredModels.length} model{filteredModels.length !== 1 ? 's' : ''} available
            </div>
          </div>
        </>
      )}
    </div>
  )
}
