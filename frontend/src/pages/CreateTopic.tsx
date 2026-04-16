import { useState, useEffect, useRef } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { useProfileNavigate } from '../utils/profileSlug'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { 
  Tag,
  Loader2, 
  Plus,
  X,
  Sparkles,
  ArrowLeft,
  Globe,
  ExternalLink,
  RefreshCw,
  Play,
  Pause,
  Trash2,
  CheckCircle,
  XCircle,
  Pencil
} from 'lucide-react'
import clsx from 'clsx'
import { topicsApi, customSitesApi, Topic, CustomSite } from '../api/client'

const PRESET_COLORS = [
  '#3B82F6', // Blue
  '#10B981', // Green
  '#8B5CF6', // Purple
  '#EF4444', // Red
  '#F97316', // Orange
  '#EC4899', // Pink
  '#06B6D4', // Cyan
  '#F59E0B', // Amber
  '#6366F1', // Indigo
  '#84CC16', // Lime
]

interface GeneratedSite {
  name: string
  url: string
}

interface PendingSite {
  name: string
  url: string
}

interface TestResult {
  siteId: string
  success: boolean
  message: string
  articles?: Array<{ title: string; url: string }>
}

export default function CreateTopic() {
  const navigate = useProfileNavigate()
  const location = useLocation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  
  const isEditing = Boolean(id)
  
  // Get the previous page from location state, default to /topics
  const previousPage = (location.state as { from?: string })?.from || '/topics'
  
  // Fetch existing topic if editing
  const { data: existingTopic, isLoading: topicLoading } = useQuery({
    queryKey: ['topic', id],
    queryFn: () => topicsApi.get(id!),
    enabled: isEditing,
    refetchOnMount: true,
  })
  
  // Fetch sites for this topic when editing
  const { data: sitesData, isLoading: sitesLoading } = useQuery({
    queryKey: ['custom-sites', id],
    queryFn: () => customSitesApi.list(id!),
    enabled: isEditing && Boolean(id),
    refetchOnMount: true,
  })
  
  const sites = sitesData?.sites || []
  
  // Topic form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(() => PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)])
  const [useNewsapi, setUseNewsapi] = useState(true)
  const [isInitialized, setIsInitialized] = useState(false)
  
  // Site management state (for create mode - pending sites)
  const [pendingSites, setPendingSites] = useState<PendingSite[]>([])
  const [siteForm, setSiteForm] = useState({ name: '', url: '' })
  
  // AI site generation state
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedSites, setGeneratedSites] = useState<GeneratedSite[]>([])
  const [selectedGeneratedSites, setSelectedGeneratedSites] = useState<Set<number>>(new Set())
  const [showGeneratedSites, setShowGeneratedSites] = useState(false)
  const [tempTopicId, setTempTopicId] = useState<string | null>(null)
  
  // Site testing state (for edit mode)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  
  // Track what we've initialized to prevent unnecessary re-initialization
  const initializedRef = useRef<{ topicId?: string; dataHash?: string }>({})
  
  // Create a simple hash of the topic data to detect changes
  const getTopicDataHash = (topic: Topic) => {
    return `${topic.id}:${topic.name}:${topic.description || ''}:${topic.color || ''}:${topic.use_newsapi}`
  }
  
  // Initialize form with existing topic data or defaults
  useEffect(() => {
    if (isEditing && existingTopic) {
      const dataHash = getTopicDataHash(existingTopic)
      // Re-initialize if topic ID changed OR data hash changed (data was updated)
      if (initializedRef.current.topicId !== existingTopic.id || initializedRef.current.dataHash !== dataHash) {
        setName(existingTopic.name)
        setDescription(existingTopic.description || '')
        setColor(existingTopic.color || PRESET_COLORS[0])
        setUseNewsapi(existingTopic.use_newsapi)
        setIsInitialized(true)
        initializedRef.current = { topicId: existingTopic.id, dataHash }
      }
    } else if (!isEditing && !isInitialized) {
      // Set defaults for new topic
      setColor(PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)])
      setIsInitialized(true)
    }
  }, [isEditing, existingTopic, isInitialized])
  
  const createTopicMutation = useMutation({
    mutationFn: async () => {
      // If we have a temp topic from site generation, use it
      if (tempTopicId) {
        // Update the temp topic with any changes
        const updatedTopic = await topicsApi.update(tempTopicId, {
          name,
          description: description || undefined,
          color,
          use_newsapi: useNewsapi,
        })
        return updatedTopic
      }
      
      // Otherwise create a new topic
      return topicsApi.create({ 
        name, 
        description: description || undefined, 
        color, 
        use_newsapi: useNewsapi, 
        enable_site_generation: true 
      })
    },
    onSuccess: async (topic) => {
      // Add all pending sites to the topic
      if (pendingSites.length > 0) {
        for (const site of pendingSites) {
          await customSitesApi.create({ 
            name: site.name, 
            url: site.url, 
            topic_id: topic.id 
          })
        }
      }
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      navigate(previousPage)
    },
  })
  
  const updateTopicMutation = useMutation({
    mutationFn: ({ id, ...options }: { id: string; name?: string; description?: string; color?: string; use_newsapi?: boolean }) =>
      topicsApi.update(id, options),
    onSuccess: (_, variables) => {
      // Invalidate both the list and the specific topic query
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      queryClient.invalidateQueries({ queryKey: ['topic', variables.id] })
      navigate(previousPage)
    },
  })
  
  // Site mutations for edit mode
  const createSiteMutation = useMutation({
    mutationFn: (data: { name: string; url: string; topic_id: string }) =>
      customSitesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites', id] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      setSiteForm({ name: '', url: '' })
    },
  })
  
  const deleteSiteMutation = useMutation({
    mutationFn: (siteId: string) => customSitesApi.delete(siteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites', id] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const toggleSiteMutation = useMutation({
    mutationFn: ({ siteId, is_active }: { siteId: string; is_active: boolean }) =>
      customSitesApi.update(siteId, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites', id] })
    },
  })
  
  const addSelectedSitesMutation = useMutation({
    mutationFn: async (sitesToAdd: GeneratedSite[]) => {
      const results = {
        success: [] as GeneratedSite[],
        failed: [] as Array<{ site: GeneratedSite; error: string }>,
      }
      
      for (const site of sitesToAdd) {
        try {
          await customSitesApi.create({
            name: site.name.trim(),
            url: site.url.trim(),
            topic_id: id!,
          })
          results.success.push(site)
        } catch (error: any) {
          const errorMessage = error?.response?.data?.detail || error?.message || 'Unknown error'
          results.failed.push({ site, error: errorMessage })
        }
      }
      
      return results
    },
    onSuccess: (results) => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites', id] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      
      // Show feedback about results
      if (results.failed.length > 0) {
        const failedMessages = results.failed.map(f => `• ${f.site.name}: ${f.error}`).join('\n')
        alert(`Added ${results.success.length} site(s) successfully.\n\nFailed to add ${results.failed.length} site(s):\n${failedMessages}`)
      } else {
        // All succeeded, close the panel
        setShowGeneratedSites(false)
        setGeneratedSites([])
        setSelectedGeneratedSites(new Set())
      }
    },
  })
  
  const handleGenerateSites = async () => {
    if (!name.trim()) {
      alert('Please enter a topic name first')
      return
    }
    
    setIsGenerating(true)
    try {
      if (isEditing && id) {
        // For edit mode, generate sites for the existing topic
        const result = await topicsApi.generateSites(id, 10)
        setGeneratedSites(result.sites)
        setSelectedGeneratedSites(new Set(result.sites.map((_, i) => i)))
        setShowGeneratedSites(true)
      } else {
        // For create mode, create a temporary topic to generate sites
        const tempTopic = await topicsApi.create({ 
          name, 
          description: description || undefined, 
          color, 
          use_newsapi: useNewsapi, 
          enable_site_generation: true 
        })
        
        setTempTopicId(tempTopic.id)
        
        try {
          const result = await topicsApi.generateSites(tempTopic.id, 10)
          setGeneratedSites(result.sites)
          setSelectedGeneratedSites(new Set(result.sites.map((_, i) => i)))
          setShowGeneratedSites(true)
        } catch (error) {
          // If generation fails, delete the temp topic
          await topicsApi.delete(tempTopic.id)
          setTempTopicId(null)
          throw error
        }
      }
    } catch (error) {
      console.error('Failed to generate sites:', error)
      alert('Failed to generate site suggestions')
    } finally {
      setIsGenerating(false)
    }
  }
  
  const handleAddSelectedGeneratedSites = () => {
    const sitesToAdd = Array.from(selectedGeneratedSites).map(i => generatedSites[i])
    
    if (isEditing) {
      // For edit mode, add sites directly to the topic
      addSelectedSitesMutation.mutate(sitesToAdd)
    } else {
      // For create mode, add to pending sites
      setPendingSites(prev => [...prev, ...sitesToAdd])
      setShowGeneratedSites(false)
      setGeneratedSites([])
      setSelectedGeneratedSites(new Set())
    }
  }
  
  const toggleSiteSelection = (index: number) => {
    setSelectedGeneratedSites(prev => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }
  
  const handleAddManualSite = (e: React.FormEvent) => {
    e.preventDefault()
    if (siteForm.name.trim() && siteForm.url.trim()) {
      if (isEditing && id) {
        // For edit mode, create site directly
        createSiteMutation.mutate({
          name: siteForm.name.trim(),
          url: siteForm.url.trim(),
          topic_id: id,
        })
      } else {
        // For create mode, add to pending sites
        setPendingSites(prev => [...prev, { ...siteForm }])
        setSiteForm({ name: '', url: '' })
      }
    }
  }
  
  const handleRemovePendingSite = (index: number) => {
    setPendingSites(prev => prev.filter((_, i) => i !== index))
  }
  
  const handleTest = async (site: CustomSite) => {
    setTestingId(site.id)
    setTestResult(null)
    
    try {
      const result = await customSitesApi.test(site.id)
      setTestResult({
        siteId: site.id,
        success: result.success,
        message: result.success ? `Found ${result.articles_found} articles` : (result.error || 'Test failed'),
        articles: result.articles,
      })
    } catch (error) {
      setTestResult({
        siteId: site.id,
        success: false,
        message: 'Failed to test site',
      })
    } finally {
      setTestingId(null)
    }
  }
  
  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleDateString()
  }
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    
    if (isEditing && id) {
      updateTopicMutation.mutate({
        id,
        name,
        description: description || undefined,
        color,
        use_newsapi: useNewsapi,
      })
    } else {
      createTopicMutation.mutate()
    }
  }
  
  const handleCancel = () => {
    // If we have a temp topic, delete it
    if (tempTopicId) {
      topicsApi.delete(tempTopicId).catch(console.error)
    }
    navigate(previousPage)
  }
  
  const isLoading = createTopicMutation.isPending || updateTopicMutation.isPending
  
  // Show loading state while fetching existing topic
  if (isEditing && topicLoading) {
    return (
      <div className="page-container flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <button
          onClick={handleCancel}
          className="flex items-center gap-2 text-augustus-400 hover:text-augustus-300 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </button>
        
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center">
            <Tag className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white">
              {isEditing ? 'Edit Topic' : 'Create New Topic'}
            </h1>
            <p className="text-sm sm:text-base text-augustus-400">
              {isEditing ? 'Update your topic settings and manage sites' : 'Create a new topic and add sites in one go'}
            </p>
          </div>
        </div>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Topic Details */}
        <div className="card">
          <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
            <Tag className="w-5 h-5 text-accent" />
            Topic Details
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="label">Topic Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Artificial Intelligence, Climate Change"
                className="input"
                required
                disabled={isLoading}
              />
            </div>
            
            <div>
              <label className="label">Color</label>
              <div className="flex gap-2 flex-wrap">
                {PRESET_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    disabled={isLoading}
                    className={clsx(
                      'w-9 h-9 sm:w-8 sm:h-8 rounded-full transition-all',
                      color === c ? 'ring-2 ring-white ring-offset-2 ring-offset-augustus-900 scale-110' : 'hover:scale-110 active:scale-95'
                    )}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
            
            <div>
              <label className="label">Description (Optional)</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of this topic"
                className="input"
                disabled={isLoading}
              />
            </div>
            
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="use-newsapi"
                checked={useNewsapi}
                onChange={(e) => setUseNewsapi(e.target.checked)}
                className="w-5 h-5 rounded border-augustus-700 bg-augustus-900 text-accent focus:ring-accent focus:ring-2"
                disabled={isLoading}
              />
              <label htmlFor="use-newsapi" className="text-sm text-augustus-300 cursor-pointer">
                Include NewsAPI results for this topic
              </label>
            </div>
          </div>
        </div>
        
        {/* AI Site Suggestions */}
        <div className="card">
          <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-accent" />
            Suggest Sites with AI
          </h2>
          
          <div className="space-y-4">
            <button
              type="button"
              onClick={handleGenerateSites}
              disabled={isGenerating || !name.trim() || isLoading || addSelectedSitesMutation.isPending}
              className="btn btn-primary flex items-center gap-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Recommend Sites with AI
                </>
              )}
            </button>
            
            {showGeneratedSites && generatedSites.length > 0 && (
              <div className="card bg-augustus-800/50 border border-augustus-700">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-white">
                    Generated Site Suggestions ({generatedSites.length})
                  </h4>
                  <button
                    type="button"
                    onClick={() => {
                      setShowGeneratedSites(false)
                      setGeneratedSites([])
                      setSelectedGeneratedSites(new Set())
                    }}
                    className="btn btn-ghost p-1"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {generatedSites.map((site, index) => (
                    <label
                      key={index}
                      className="flex items-start gap-2 p-2 rounded hover:bg-augustus-700/50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedGeneratedSites.has(index)}
                        onChange={() => toggleSiteSelection(index)}
                        className="mt-1 w-4 h-4 rounded border-augustus-700 bg-augustus-900 text-accent focus:ring-accent focus:ring-2"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-white">{site.name}</div>
                        <div className="text-xs text-augustus-400 truncate">{site.url}</div>
                      </div>
                    </label>
                  ))}
                </div>
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-augustus-700">
                  <button
                    type="button"
                    onClick={handleAddSelectedGeneratedSites}
                    disabled={selectedGeneratedSites.size === 0 || addSelectedSitesMutation.isPending}
                    className="btn btn-primary flex items-center gap-2"
                  >
                    {addSelectedSitesMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Adding...
                      </>
                    ) : (
                      <>
                        <Plus className="w-4 h-4" />
                        Add Selected ({selectedGeneratedSites.size})
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowGeneratedSites(false)
                      setGeneratedSites([])
                      setSelectedGeneratedSites(new Set())
                    }}
                    className="btn btn-ghost"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
        
        {/* Add Sites Manually */}
        <div className="card">
          <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
            <Plus className="w-5 h-5 text-accent" />
            Add Sites Manually
          </h2>
          
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                type="text"
                value={siteForm.name}
                onChange={(e) => setSiteForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="Site name"
                className="input"
              />
              <input
                type="url"
                value={siteForm.url}
                onChange={(e) => setSiteForm(prev => ({ ...prev, url: e.target.value }))}
                placeholder="https://example.com"
                className="input"
              />
            </div>
            <button
              type="button"
              onClick={handleAddManualSite}
              disabled={!siteForm.name.trim() || !siteForm.url.trim() || createSiteMutation.isPending}
              className="btn btn-secondary flex items-center gap-2"
            >
              {createSiteMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  Add Site
                </>
              )}
            </button>
          </div>
        </div>
        
        {/* Pending Sites List (Create mode only) */}
        {!isEditing && pendingSites.length > 0 && (
          <div className="card">
            <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">
              Sites to Add ({pendingSites.length})
            </h2>
            
            <div className="space-y-2">
              {pendingSites.map((site, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-augustus-800/30 rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-white text-sm">{site.name}</div>
                    <div className="text-xs text-augustus-400 truncate">{site.url}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemovePendingSite(index)}
                    className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Existing Sites List (Edit mode only) */}
        {isEditing && (
          <div className="card">
            <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
              <Globe className="w-5 h-5 text-accent" />
              Sites ({sites.length})
            </h2>
            
            {sitesLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="w-6 h-6 animate-spin text-accent" />
              </div>
            ) : sites.length === 0 ? (
              <div className="text-center py-6 text-augustus-400 text-sm">
                No sites yet. Add one manually or generate suggestions!
              </div>
            ) : (
              <div className="space-y-2">
                {sites.map((site) => (
                  <div
                    key={site.id}
                    className="card bg-augustus-800/30 hover:bg-augustus-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={clsx(
                          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                          site.is_active
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-augustus-800 text-augustus-500'
                        )}
                      >
                        <Globe className="w-4 h-4" />
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-white text-sm">{site.name}</div>
                        <a
                          href={site.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-augustus-400 hover:text-accent truncate flex items-center gap-1"
                        >
                          <span className="truncate">{site.url}</span>
                          <ExternalLink className="w-3 h-3 flex-shrink-0" />
                        </a>
                        <div className="flex items-center gap-2 text-xs text-augustus-500 mt-1">
                          <span>Last: {formatDate(site.last_fetched)}</span>
                          {site.last_error && (
                            <span className="text-red-400 flex items-center gap-1">
                              <XCircle className="w-3 h-3" />
                              Error
                            </span>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => handleTest(site)}
                          disabled={testingId === site.id}
                          className="btn btn-ghost p-2"
                          title="Test fetch"
                        >
                          {testingId === site.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <RefreshCw className="w-4 h-4" />
                          )}
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => navigate(`/sites/${site.id}/edit`, { state: { from: `/topics/${id}/edit` } })}
                          className="btn btn-ghost p-2 text-augustus-400 hover:text-accent"
                          title="Edit"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => toggleSiteMutation.mutate({
                            siteId: site.id,
                            is_active: !site.is_active,
                          })}
                          className={clsx(
                            'btn btn-ghost p-2',
                            site.is_active ? 'text-green-400' : 'text-augustus-500'
                          )}
                          title={site.is_active ? 'Disable site' : 'Enable site'}
                        >
                          {site.is_active ? (
                            <Pause className="w-4 h-4" />
                          ) : (
                            <Play className="w-4 h-4" />
                          )}
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => deleteSiteMutation.mutate(site.id)}
                          className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    
                    {/* Test result */}
                    {testResult && testResult.siteId === site.id && (
                      <div className={clsx(
                        'mt-3 pt-3 border-t border-augustus-800/50',
                        testResult.success ? 'text-green-400' : 'text-red-400'
                      )}>
                        <div className="flex items-center gap-2 mb-2">
                          {testResult.success ? (
                            <CheckCircle className="w-4 h-4 flex-shrink-0" />
                          ) : (
                            <XCircle className="w-4 h-4 flex-shrink-0" />
                          )}
                          <span className="text-sm font-medium">{testResult.message}</span>
                        </div>
                        
                        {testResult.articles && testResult.articles.length > 0 && (
                          <div className="space-y-1 pl-6">
                            {testResult.articles.slice(0, 3).map((article, i) => (
                              <a
                                key={i}
                                href={article.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-augustus-400 hover:text-accent block truncate"
                              >
                                • {article.title}
                              </a>
                            ))}
                            {testResult.articles.length > 3 && (
                              <span className="text-xs text-augustus-500">
                                ...and {testResult.articles.length - 3} more
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {/* Submit Button */}
        <div className="flex flex-col-reverse sm:flex-row items-center gap-3">
          <button
            type="button"
            onClick={handleCancel}
            className="btn btn-ghost w-full sm:w-auto"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!name.trim() || isLoading}
            className="btn btn-primary w-full sm:w-auto flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {isEditing ? 'Updating...' : 'Creating...'}
              </>
            ) : (
              <>
                {isEditing ? 'Update Topic' : 'Create Topic'}
              </>
            )}
          </button>
        </div>
        
        {(createTopicMutation.isError || updateTopicMutation.isError) && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-400">
              {(createTopicMutation.error as Error)?.message || (updateTopicMutation.error as Error)?.message || 'Failed to save topic'}
            </p>
          </div>
        )}
      </form>
    </div>
  )
}
