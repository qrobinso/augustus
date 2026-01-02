import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Tag,
  Loader2, 
  Plus,
  Trash2,
  AlertCircle,
  Globe,
  Pencil,
  X,
  ExternalLink,
  CheckCircle,
  XCircle,
  Sparkles,
  ArrowUpDown,
  Wand2
} from 'lucide-react'
import clsx from 'clsx'
import { topicsApi, customSitesApi, Topic, CustomSite, GeneratedTopicFromPrompt } from '../api/client'

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

export default function Topics() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  // Sort state - persisted to localStorage
  const [sortBy, setSortBy] = useState<{
    field: 'created_at' | 'site_count' | 'use_newsapi' | 'name'
    direction: 'asc' | 'desc'
  }>(() => {
    const saved = localStorage.getItem('topicsSortBy')
    return saved !== null ? JSON.parse(saved) : { field: 'created_at', direction: 'desc' }
  })
  
  // Prompt-based topic generation state
  const [topicPrompt, setTopicPrompt] = useState('')
  const [isGeneratingFromPrompt, setIsGeneratingFromPrompt] = useState(false)
  const [generatedTopic, setGeneratedTopic] = useState<GeneratedTopicFromPrompt | null>(null)
  const [generatedTopicColor, setGeneratedTopicColor] = useState(PRESET_COLORS[0])
  const [selectedGeneratedSites, setSelectedGeneratedSites] = useState<Set<number>>(new Set())
  const [isCreatingGeneratedTopic, setIsCreatingGeneratedTopic] = useState(false)
  const [promptError, setPromptError] = useState<string | null>(null)
  
  // Save sort preference to localStorage
  useEffect(() => {
    localStorage.setItem('topicsSortBy', JSON.stringify(sortBy))
  }, [sortBy])
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  // Fetch sites for all topics
  const topicIds = data?.topics.map(t => t.id) || []
  const sitesQueries = useQuery({
    queryKey: ['custom-sites', topicIds],
    queryFn: async () => {
      const results: Record<string, CustomSite[]> = {}
      for (const topicId of topicIds) {
        const data = await customSitesApi.list(topicId)
        results[topicId] = data.sites
      }
      return results
    },
    enabled: topicIds.length > 0,
  })
  
  const deleteTopicMutation = useMutation({
    mutationFn: (id: string) => topicsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
    },
  })
  
  // Handle generating topic from prompt
  const handleGenerateFromPrompt = async () => {
    if (!topicPrompt.trim()) return
    
    setIsGeneratingFromPrompt(true)
    setPromptError(null)
    setGeneratedTopic(null)
    
    try {
      const result = await topicsApi.generateFromPrompt(topicPrompt.trim())
      setGeneratedTopic(result)
      // Select all sites by default
      setSelectedGeneratedSites(new Set(result.sites.map((_, i) => i)))
      // Reset color
      setGeneratedTopicColor(PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)])
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate topic'
      setPromptError(errorMessage)
    } finally {
      setIsGeneratingFromPrompt(false)
    }
  }
  
  // Normalize URL for duplicate checking (remove trailing slash, lowercase)
  const normalizeUrl = (url: string): string => {
    return url.trim().toLowerCase().replace(/\/$/, '')
  }
  
  // Handle creating the generated topic
  const handleCreateGeneratedTopic = async () => {
    if (!generatedTopic) return
    
    setIsCreatingGeneratedTopic(true)
    setPromptError(null)
    
    try {
      // Create the topic
      const newTopic = await topicsApi.create({
        name: generatedTopic.name,
        description: generatedTopic.description,
        color: generatedTopicColor,
        use_newsapi: generatedTopic.use_newsapi,
      })
      
      // Get all existing sites to check for duplicates
      const existingSitesData = await customSitesApi.list()
      const existingUrls = new Set(
        existingSitesData.sites.map(site => normalizeUrl(site.url))
      )
      
      // Add selected sites, filtering out duplicates
      const selectedSitesList = Array.from(selectedGeneratedSites).map(i => generatedTopic.sites[i])
      const seenUrls = new Set<string>()
      const sitesToCreate: Array<{ name: string; url: string }> = []
      
      for (const site of selectedSitesList) {
        const normalizedUrl = normalizeUrl(site.url)
        
        // Skip if already seen in this batch or exists in database
        if (seenUrls.has(normalizedUrl) || existingUrls.has(normalizedUrl)) {
          continue
        }
        
        seenUrls.add(normalizedUrl)
        sitesToCreate.push(site)
      }
      
      // Create sites, continuing even if some fail
      const errors: string[] = []
      let successCount = 0
      
      for (const site of sitesToCreate) {
        try {
          await customSitesApi.create({
            name: site.name,
            url: site.url,
            topic_id: newTopic.id,
          })
          successCount++
        } catch (err: unknown) {
          const errorMsg = err instanceof Error ? err.message : 'Unknown error'
          errors.push(`${site.name}: ${errorMsg}`)
        }
      }
      
      // Show errors if any, but don't fail the whole operation
      if (errors.length > 0) {
        setPromptError(
          `Created ${successCount} site(s), but ${errors.length} failed: ${errors.join('; ')}`
        )
      }
      
      // Refresh data and reset state
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      
      // Only clear the form if all sites were created successfully
      if (errors.length === 0) {
        setGeneratedTopic(null)
        setTopicPrompt('')
        setSelectedGeneratedSites(new Set())
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create topic'
      setPromptError(errorMessage)
    } finally {
      setIsCreatingGeneratedTopic(false)
    }
  }
  
  // Toggle site selection for generated topic
  const toggleGeneratedSiteSelection = (index: number) => {
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
  
  // Cancel/dismiss generated topic
  const dismissGeneratedTopic = () => {
    setGeneratedTopic(null)
    setSelectedGeneratedSites(new Set())
    setPromptError(null)
  }
  
  // Sort topics based on selected sort option
  const sortedTopics = useMemo(() => {
    if (!data?.topics) return []
    
    const topics = [...data.topics]
    
    topics.sort((a, b) => {
      switch (sortBy.field) {
        case 'created_at':
          const dateA = new Date(a.created_at).getTime()
          const dateB = new Date(b.created_at).getTime()
          return sortBy.direction === 'desc' ? dateB - dateA : dateA - dateB
          
        case 'site_count':
          return sortBy.direction === 'desc' 
            ? b.site_count - a.site_count 
            : a.site_count - b.site_count
          
        case 'use_newsapi':
          // NewsAPI enabled first when desc, disabled first when asc
          if (sortBy.direction === 'desc') {
            return (b.use_newsapi ? 1 : 0) - (a.use_newsapi ? 1 : 0)
          } else {
            return (a.use_newsapi ? 1 : 0) - (b.use_newsapi ? 1 : 0)
          }
          
        case 'name':
          return sortBy.direction === 'desc'
            ? b.name.localeCompare(a.name)
            : a.name.localeCompare(b.name)
          
        default:
          return 0
      }
    })
    
    return topics
  }, [data?.topics, sortBy])
  
  const sitesByTopic = sitesQueries.data || {}
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          Topics
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Manage your news topics and their associated websites
        </p>
      </div>
      
      {/* AI Topic Generator */}
      <div className="card mb-6 sm:mb-8 bg-gradient-to-br from-augustus-800/50 to-augustus-900/50 border-augustus-700/50">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
            <Wand2 className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h2 className="font-semibold text-white text-base sm:text-lg">Create Topic with AI</h2>
            <p className="text-sm text-augustus-400 mt-0.5">
              Describe what you want to follow in plain text, and AI will create a topic with recommended sources
            </p>
          </div>
        </div>
        
        <div className="space-y-4">
          <div className="relative">
            <textarea
              value={topicPrompt}
              onChange={(e) => setTopicPrompt(e.target.value)}
              placeholder="e.g. I want to follow the latest developments in electric vehicles and sustainable transportation..."
              className="input min-h-[80px] sm:min-h-[100px] resize-none pr-4"
              disabled={isGeneratingFromPrompt}
            />
          </div>
          
          <div className="flex flex-col gap-3">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <button
                onClick={handleGenerateFromPrompt}
                disabled={!topicPrompt.trim() || isGeneratingFromPrompt}
                className="btn btn-primary flex items-center justify-center gap-2"
              >
                {isGeneratingFromPrompt ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Generate Topic
                  </>
                )}
              </button>
              
              {promptError && (
                <div className="flex items-center gap-2 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{promptError}</span>
                </div>
              )}
            </div>
            
            <button
              onClick={() => navigate('/topics/create', { state: { from: '/topics' } })}
              className="text-sm text-augustus-400 hover:text-accent transition-colors text-center self-center"
            >
              Manually Add Topic
            </button>
          </div>
        </div>
        
        {/* Generated Topic Preview */}
        {generatedTopic && (
          <div className="mt-6 pt-6 border-t border-augustus-700/50">
            <div className="flex items-start justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                <h3 className="font-semibold text-white">Generated Topic</h3>
              </div>
              <button
                onClick={dismissGeneratedTopic}
                className="btn btn-ghost p-1.5 text-augustus-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="space-y-4">
              {/* Topic Name & Description */}
              <div className="card bg-augustus-800/50">
                <div className="flex items-start gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: `${generatedTopicColor}20` }}
                  >
                    <Tag className="w-5 h-5" style={{ color: generatedTopicColor }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-white text-base">{generatedTopic.name}</h4>
                    <p className="text-sm text-augustus-400 mt-1">{generatedTopic.description}</p>
                  </div>
                </div>
                
                {/* Color picker */}
                <div className="mt-4 flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-augustus-500">Color:</span>
                  {PRESET_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setGeneratedTopicColor(c)}
                      className={clsx(
                        'w-6 h-6 rounded-full transition-all',
                        generatedTopicColor === c ? 'ring-2 ring-white ring-offset-2 ring-offset-augustus-800' : 'hover:scale-110'
                      )}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>
              
              {/* NewsAPI Recommendation */}
              <div className={clsx(
                'card flex items-start gap-3',
                generatedTopic.use_newsapi ? 'bg-green-500/10 border-green-500/20' : 'bg-augustus-800/50'
              )}>
                <div className={clsx(
                  'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                  generatedTopic.use_newsapi ? 'bg-green-500/20' : 'bg-augustus-700'
                )}>
                  {generatedTopic.use_newsapi ? (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-augustus-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={clsx(
                      'text-sm font-medium',
                      generatedTopic.use_newsapi ? 'text-green-400' : 'text-augustus-300'
                    )}>
                      NewsAPI: {generatedTopic.use_newsapi ? 'Recommended' : 'Not Recommended'}
                    </span>
                  </div>
                  <p className="text-xs text-augustus-400 mt-1">{generatedTopic.reasoning}</p>
                </div>
              </div>
              
              {/* Suggested Sites */}
              {generatedTopic.sites.length > 0 && (
                <div className="card bg-augustus-800/50">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Globe className="w-4 h-4 text-augustus-400" />
                      Recommended Sites ({generatedTopic.sites.length})
                    </h4>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setSelectedGeneratedSites(new Set(generatedTopic.sites.map((_, i) => i)))}
                        className="text-xs text-accent hover:underline"
                      >
                        Select All
                      </button>
                      <span className="text-augustus-600">|</span>
                      <button
                        onClick={() => setSelectedGeneratedSites(new Set())}
                        className="text-xs text-augustus-400 hover:text-white"
                      >
                        Deselect All
                      </button>
                    </div>
                  </div>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {generatedTopic.sites.map((site, index) => (
                      <label
                        key={index}
                        className="flex items-start gap-2 p-2 rounded hover:bg-augustus-700/50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedGeneratedSites.has(index)}
                          onChange={() => toggleGeneratedSiteSelection(index)}
                          className="mt-1 w-4 h-4 rounded border-augustus-700 bg-augustus-900 text-accent focus:ring-accent focus:ring-2"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-white">{site.name}</div>
                          <div className="text-xs text-augustus-400 truncate">{site.url}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Create Button */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleCreateGeneratedTopic}
                  disabled={isCreatingGeneratedTopic}
                  className="btn btn-primary flex items-center gap-2"
                >
                  {isCreatingGeneratedTopic ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      Create Topic
                      {selectedGeneratedSites.size > 0 && ` with ${selectedGeneratedSites.size} Sites`}
                    </>
                  )}
                </button>
                <button
                  onClick={dismissGeneratedTopic}
                  className="btn btn-ghost"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Sort dropdown - above topics list */}
      {data && data.topics.length > 0 && (
        <div className="mb-4 flex items-center justify-end">
          <div className="relative w-full sm:w-auto sm:min-w-[200px]">
            <select
              value={`${sortBy.field}-${sortBy.direction}`}
              onChange={(e) => {
                const [field, direction] = e.target.value.split('-') as [typeof sortBy.field, typeof sortBy.direction]
                setSortBy({ field, direction })
              }}
              className="input appearance-none pr-8 cursor-pointer text-sm"
            >
              <option value="created_at-desc">Newest First</option>
              <option value="created_at-asc">Oldest First</option>
              <option value="site_count-desc">Most Sites</option>
              <option value="site_count-asc">Least Sites</option>
              <option value="use_newsapi-desc">NewsAPI Enabled</option>
              <option value="use_newsapi-asc">NewsAPI Disabled</option>
              <option value="name-asc">Name (A-Z)</option>
              <option value="name-desc">Name (Z-A)</option>
            </select>
            <ArrowUpDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-augustus-400 pointer-events-none" />
          </div>
        </div>
      )}
      
      {/* Topics list */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="card flex items-center justify-center py-10 sm:py-12">
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="card text-center py-10 sm:py-12">
            <AlertCircle className="w-10 sm:w-12 h-10 sm:h-12 text-red-500 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">Failed to load topics. Is the backend running?</p>
          </div>
        ) : data?.topics.length === 0 ? (
          <div className="card text-center py-10 sm:py-12">
            <Tag className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">No topics yet. Add your first one!</p>
          </div>
        ) : (
          <div className="space-y-3 sm:space-y-4">
            {sortedTopics.map((topic) => {
              const sites = sitesByTopic[topic.id] || []
              const isLoadingSites = sitesQueries.isLoading
              
              return (
                <div
                  key={topic.id}
                  className="card hover:border-augustus-700 transition-colors"
                >
                  {/* Topic Header */}
                  <div className="flex items-start gap-3 mb-4">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: `${topic.color}20` }}
                    >
                      <Tag 
                        className="w-5 h-5" 
                        style={{ color: topic.color || '#3B82F6' }} 
                      />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-white text-sm sm:text-base">{topic.name}</h3>
                      {topic.description && (
                        <p className="text-xs sm:text-sm text-augustus-400 mt-1">
                          {topic.description}
                        </p>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => navigate(`/topics/${topic.id}/edit`, { state: { from: '/topics' } })}
                        className="btn btn-ghost p-2 sm:p-2 min-h-[44px] min-w-[44px] touch-target text-augustus-400 hover:text-white"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4 sm:w-5 sm:h-5" />
                      </button>
                      <button
                        onClick={() => {
                          if (topic.site_count > 0) {
                            if (!confirm(`This will also delete ${topic.site_count} custom site(s) linked to this topic. Continue?`)) {
                              return
                            }
                          }
                          deleteTopicMutation.mutate(topic.id)
                        }}
                        className="btn btn-ghost p-2 sm:p-2 min-h-[44px] min-w-[44px] touch-target text-augustus-500 hover:text-red-400"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4 sm:w-5 sm:h-5" />
                      </button>
                    </div>
                  </div>
                  
                  {/* NewsAPI Status */}
                  <div className="mb-4">
                    <div className={clsx(
                      'flex items-center gap-2 px-3 py-2 rounded-lg',
                      topic.use_newsapi 
                        ? 'bg-green-500/10 border border-green-500/20' 
                        : 'bg-augustus-800/50 border border-augustus-700'
                    )}>
                      {topic.use_newsapi ? (
                        <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                      ) : (
                        <XCircle className="w-4 h-4 text-augustus-500 flex-shrink-0" />
                      )}
                      <span className={clsx(
                        'text-sm font-medium',
                        topic.use_newsapi ? 'text-green-400' : 'text-augustus-400'
                      )}>
                        NewsAPI: {topic.use_newsapi ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                  
                  {/* Sites List */}
                  <div>
                    <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                      <Globe className="w-4 h-4 text-augustus-400" />
                      Custom Sites ({sites.length})
                    </h4>
                    
                    {isLoadingSites ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="w-5 h-5 animate-spin text-accent" />
                      </div>
                    ) : sites.length === 0 ? (
                      <div className="text-center py-4 text-augustus-400 text-sm">
                        No custom sites added yet
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {sites.map((site) => (
                          <div
                            key={site.id}
                            className="flex items-center gap-3 p-2 bg-augustus-800/30 rounded-lg"
                          >
                            <div
                              className={clsx(
                                'w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0',
                                site.is_active
                                  ? 'bg-green-500/20 text-green-400'
                                  : 'bg-augustus-800 text-augustus-500'
                              )}
                            >
                              <Globe className="w-3 h-3" />
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
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
