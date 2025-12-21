import { useState } from 'react'
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
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Play,
  Pause,
  RefreshCw,
  CheckCircle,
  XCircle,
  Sparkles
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

export default function Topics() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  // Topic editing state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editColor, setEditColor] = useState('')
  const [editUseNewsapi, setEditUseNewsapi] = useState(true)
  
  // Expanded topics (showing sites)
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set())
  
  // Site management per topic
  const [siteForms, setSiteForms] = useState<Record<string, { name: string; url: string }>>({})
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{
    siteId: string
    success: boolean
    message: string
    articles?: Array<{ title: string; url: string }>
  } | null>(null)
  
  // Site generation state
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null)
  const [generatedSites, setGeneratedSites] = useState<Record<string, GeneratedSite[]>>({})
  const [selectedSites, setSelectedSites] = useState<Record<string, Set<number>>>({})
  const [showGeneratedSites, setShowGeneratedSites] = useState<Record<string, boolean>>({})
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  // Fetch sites for expanded topics
  const expandedTopicIds = Array.from(expandedTopics)
  const sitesQueries = useQuery({
    queryKey: ['custom-sites', expandedTopicIds],
    queryFn: async () => {
      const results: Record<string, CustomSite[]> = {}
      for (const topicId of expandedTopicIds) {
        const data = await customSitesApi.list(topicId)
        results[topicId] = data.sites
      }
      return results
    },
    enabled: expandedTopicIds.length > 0,
  })
  
  
  const updateTopicMutation = useMutation({
    mutationFn: ({ id, ...options }: { id: string; name?: string; description?: string; color?: string; use_newsapi?: boolean }) =>
      topicsApi.update(id, options),
    onSuccess: () => {
      setEditingId(null)
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const deleteTopicMutation = useMutation({
    mutationFn: (id: string) => topicsApi.delete(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['topics'] })
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      // Remove from expanded if deleted
      setExpandedTopics(prev => {
        const next = new Set(prev)
        next.delete(deletedId)
        return next
      })
      // Clean up all state related to the deleted topic
      setSiteForms(prev => {
        const next = { ...prev }
        delete next[deletedId]
        return next
      })
      setGeneratedSites(prev => {
        const next = { ...prev }
        delete next[deletedId]
        return next
      })
      setSelectedSites(prev => {
        const next = { ...prev }
        delete next[deletedId]
        return next
      })
      setShowGeneratedSites(prev => {
        const next = { ...prev }
        delete next[deletedId]
        return next
      })
      // Clear test result - it will be invalidated anyway when sites query updates
      setTestResult(null)
      // Clear generating state if it was for this topic
      setGeneratingTopicId(prev => prev === deletedId ? null : prev)
    },
  })
  
  const createSiteMutation = useMutation({
    mutationFn: ({ topicId, name, url }: { topicId: string; name: string; url: string }) =>
      customSitesApi.create({ name, url, topic_id: topicId }),
    onSuccess: (_, variables) => {
      setSiteForms(prev => ({ ...prev, [variables.topicId]: { name: '', url: '' } }))
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const deleteSiteMutation = useMutation({
    mutationFn: (id: string) => customSitesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const toggleSiteMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      customSitesApi.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
    },
  })
  
  const generateSitesMutation = useMutation({
    mutationFn: (topicId: string) => topicsApi.generateSites(topicId, 10),
    onSuccess: (data, topicId) => {
      setGeneratedSites(prev => ({ ...prev, [topicId]: data.sites }))
      setShowGeneratedSites(prev => ({ ...prev, [topicId]: true }))
      setSelectedSites(prev => ({ ...prev, [topicId]: new Set(data.sites.map((_, i) => i)) }))
      setGeneratingTopicId(null)
    },
    onError: () => {
      setGeneratingTopicId(null)
    },
  })
  
  const addSelectedSitesMutation = useMutation({
    mutationFn: async ({ topicId, sites, indices }: { topicId: string; sites: GeneratedSite[]; indices: number[] }) => {
      const selectedSites = indices.map(i => sites[i])
      for (const site of selectedSites) {
        await customSitesApi.create({ name: site.name, url: site.url, topic_id: topicId })
      }
    },
    onSuccess: (_, variables) => {
      setShowGeneratedSites(prev => ({ ...prev, [variables.topicId]: false }))
      setGeneratedSites(prev => {
        const next = { ...prev }
        delete next[variables.topicId]
        return next
      })
      setSelectedSites(prev => {
        const next = { ...prev }
        delete next[variables.topicId]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const toggleExpand = (topicId: string) => {
    setExpandedTopics(prev => {
      const next = new Set(prev)
      if (next.has(topicId)) {
        next.delete(topicId)
      } else {
        next.add(topicId)
      }
      return next
    })
  }
  
  const startEdit = (topic: Topic) => {
    setEditingId(topic.id)
    setEditName(topic.name)
    setEditDescription(topic.description || '')
    setEditColor(topic.color || PRESET_COLORS[0])
    setEditUseNewsapi(topic.use_newsapi)
  }
  
  const cancelEdit = () => {
    setEditingId(null)
    setEditName('')
    setEditDescription('')
    setEditColor('')
    setEditUseNewsapi(true)
  }
  
  const saveEdit = (id: string) => {
    updateTopicMutation.mutate({
      id,
      name: editName,
      description: editDescription || undefined,
      color: editColor,
      use_newsapi: editUseNewsapi,
    })
  }
  
  const handleCreateSite = (e: React.FormEvent, topicId: string) => {
    e.preventDefault()
    const form = siteForms[topicId] || { name: '', url: '' }
    if (form.name.trim() && form.url.trim()) {
      createSiteMutation.mutate({ topicId, name: form.name, url: form.url })
    }
  }
  
  const handleGenerateSites = (topicId: string) => {
    setGeneratingTopicId(topicId)
    generateSitesMutation.mutate(topicId)
  }
  
  const handleAddSelectedSites = (topicId: string) => {
    const sites = generatedSites[topicId] || []
    const indices = Array.from(selectedSites[topicId] || [])
    if (indices.length > 0) {
      addSelectedSitesMutation.mutate({ topicId, sites, indices })
    }
  }
  
  const toggleSiteSelection = (topicId: string, index: number) => {
    setSelectedSites(prev => {
      const next = { ...prev }
      const currentSet = next[topicId] || new Set()
      const newSet = new Set(currentSet)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      next[topicId] = newSet
      return next
    })
  }
  
  const handleTest = async (site: CustomSite) => {
    setTestingId(site.id)
    setTestResult(null)
    
    try {
      const result = await customSitesApi.test(site.id)
      setTestResult({
        siteId: site.id,
        success: result.success,
        message: result.success 
          ? `Found ${result.articles_found} articles`
          : result.error || 'Failed to fetch articles',
        articles: result.articles,
      })
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
    } catch (err) {
      setTestResult({
        siteId: site.id,
        success: false,
        message: 'Failed to test site',
      })
    } finally {
      setTestingId(null)
    }
  }
  
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Never'
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  }
  
  const sitesByTopic = sitesQueries.data || {}
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
            Topics & Sites
          </h1>
          <p className="text-sm sm:text-base text-augustus-400">
            Manage your news topics and their associated websites
          </p>
        </div>
        <button
          onClick={() => navigate('/topics/create', { state: { from: '/topics' } })}
          className="btn btn-primary flex items-center gap-2 w-full sm:w-auto"
        >
          <Plus className="w-5 h-5" />
          Create Topic
        </button>
      </div>
      
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
            {data?.topics.map((topic) => {
              const isExpanded = expandedTopics.has(topic.id)
              const sites = sitesByTopic[topic.id] || []
              const isLoadingSites = sitesQueries.isLoading && isExpanded
              const siteForm = siteForms[topic.id] || { name: '', url: '' }
              const generatedSitesForTopic = generatedSites[topic.id] || []
              const showGenerated = showGeneratedSites[topic.id] || false
              const selectedIndices = selectedSites[topic.id] || new Set()
              
              return (
                <div
                  key={topic.id}
                  className="card hover:border-augustus-700 transition-colors"
                >
                  {editingId === topic.id ? (
                    // Edit mode
                    <div className="space-y-3">
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="input"
                        autoFocus
                      />
                      <input
                        type="text"
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        placeholder="Description (optional)"
                        className="input"
                      />
                      <div className="flex gap-2 flex-wrap">
                        {PRESET_COLORS.map((c) => (
                          <button
                            key={c}
                            type="button"
                            onClick={() => setEditColor(c)}
                            className={clsx(
                              'w-7 h-7 sm:w-6 sm:h-6 rounded-full transition-all',
                              editColor === c ? 'ring-2 ring-white ring-offset-2 ring-offset-augustus-900' : 'hover:scale-110'
                            )}
                            style={{ backgroundColor: c }}
                          />
                        ))}
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          id={`edit-use-newsapi-${topic.id}`}
                          checked={editUseNewsapi}
                          onChange={(e) => setEditUseNewsapi(e.target.checked)}
                          className="w-5 h-5 rounded border-augustus-700 bg-augustus-900 text-accent focus:ring-accent focus:ring-2"
                        />
                        <label htmlFor={`edit-use-newsapi-${topic.id}`} className="text-sm text-augustus-300 cursor-pointer">
                          Include NewsAPI results
                        </label>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => saveEdit(topic.id)}
                          disabled={updateTopicMutation.isPending}
                          className="btn btn-primary flex-1 flex items-center justify-center gap-1"
                        >
                          {updateTopicMutation.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4" />
                          )}
                          Save
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="btn btn-ghost p-2"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    // View mode
                    <>
                      <div 
                        className="flex items-start gap-3 cursor-pointer"
                        onClick={() => toggleExpand(topic.id)}
                      >
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
                            <p className="text-xs sm:text-sm text-augustus-400 truncate">
                              {topic.description}
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-1.5 sm:mt-2 text-xs text-augustus-500">
                            <Globe className="w-3 h-3" />
                            <span>{topic.site_count} site{topic.site_count !== 1 ? 's' : ''}</span>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-1">
                            {isExpanded ? (
                              <ChevronUp className="w-5 h-5 text-augustus-400" />
                            ) : (
                              <ChevronDown className="w-5 h-5 text-augustus-400" />
                            )}
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              startEdit(topic)
                            }}
                            className="btn btn-ghost p-2 sm:p-2 min-h-[44px] min-w-[44px] touch-target text-augustus-400 hover:text-white"
                            title="Edit"
                          >
                            <Pencil className="w-4 h-4 sm:w-5 sm:h-5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
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
                      
                      {/* Expanded sites section */}
                      {isExpanded && (
                        <div className="mt-4 pt-4 border-t border-augustus-800/50 space-y-4">
                          {/* NewsAPI Status Toggle */}
                          <button
                            onClick={() => {
                              updateTopicMutation.mutate({
                                id: topic.id,
                                use_newsapi: !topic.use_newsapi,
                              })
                            }}
                            disabled={updateTopicMutation.isPending}
                            className={clsx(
                              'w-full flex items-center gap-2 px-4 py-3 sm:py-3 rounded-lg transition-all touch-target min-h-[48px] text-left',
                              topic.use_newsapi 
                                ? 'bg-green-500/10 border border-green-500/20 hover:bg-green-500/15 active:bg-green-500/20' 
                                : 'bg-augustus-800/50 border border-augustus-700 hover:bg-augustus-800/70 active:bg-augustus-800'
                            )}
                          >
                            {updateTopicMutation.isPending ? (
                              <Loader2 className="w-5 h-5 animate-spin text-augustus-400 flex-shrink-0" />
                            ) : topic.use_newsapi ? (
                              <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                            ) : (
                              <XCircle className="w-5 h-5 text-augustus-500 flex-shrink-0" />
                            )}
                            <span className={clsx(
                              'text-sm sm:text-base font-medium flex-1',
                              topic.use_newsapi ? 'text-green-400' : 'text-augustus-400'
                            )}>
                              NewsAPI: {topic.use_newsapi ? 'Enabled' : 'Disabled'}
                            </span>
                            {!topic.use_newsapi && (
                              <span className="text-xs text-augustus-500 hidden sm:inline">
                                (Only custom sites will be used)
                              </span>
                            )}
                          </button>
                          
                          {/* Recommend Sites Button */}
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleGenerateSites(topic.id)}
                              disabled={generatingTopicId === topic.id || !topic.name.trim()}
                              className="btn btn-primary flex items-center gap-2"
                            >
                              {generatingTopicId === topic.id ? (
                                <>
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                  Recommending...
                                </>
                              ) : (
                                <>
                                  <Sparkles className="w-4 h-4" />
                                  Recommend Sites with AI
                                </>
                              )}
                            </button>
                            {generateSitesMutation.isError && generatingTopicId === topic.id && (
                              <span className="text-sm text-red-400">
                                Failed to generate sites
                              </span>
                            )}
                          </div>
                          
                          {/* Generated Sites Modal/Panel */}
                          {showGenerated && generatedSitesForTopic.length > 0 && (
                            <div className="card bg-augustus-800/50 border border-augustus-700">
                              <div className="flex items-center justify-between mb-3">
                                <h4 className="text-sm font-semibold text-white">
                                  Generated Site Suggestions ({generatedSitesForTopic.length})
                                </h4>
                                <button
                                  onClick={() => setShowGeneratedSites(prev => ({ ...prev, [topic.id]: false }))}
                                  className="btn btn-ghost p-1"
                                >
                                  <X className="w-4 h-4" />
                                </button>
                              </div>
                              <div className="space-y-2 max-h-64 overflow-y-auto">
                                {generatedSitesForTopic.map((site, index) => (
                                  <label
                                    key={index}
                                    className="flex items-start gap-2 p-2 rounded hover:bg-augustus-700/50 cursor-pointer"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selectedIndices.has(index)}
                                      onChange={() => toggleSiteSelection(topic.id, index)}
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
                                  onClick={() => handleAddSelectedSites(topic.id)}
                                  disabled={selectedIndices.size === 0 || addSelectedSitesMutation.isPending}
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
                                      Add Selected ({selectedIndices.size})
                                    </>
                                  )}
                                </button>
                                <button
                                  onClick={() => setShowGeneratedSites(prev => ({ ...prev, [topic.id]: false }))}
                                  className="btn btn-ghost"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          )}
                          
                          {/* Add Site Form */}
                          <form onSubmit={(e) => handleCreateSite(e, topic.id)} className="card bg-augustus-800/30">
                            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                              <Plus className="w-4 h-4" />
                              Add New Site
                            </h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <input
                                type="text"
                                value={siteForm.name}
                                onChange={(e) => setSiteForms(prev => ({
                                  ...prev,
                                  [topic.id]: { ...siteForm, name: e.target.value }
                                }))}
                                placeholder="Site name"
                                className="input"
                              />
                              <input
                                type="url"
                                value={siteForm.url}
                                onChange={(e) => setSiteForms(prev => ({
                                  ...prev,
                                  [topic.id]: { ...siteForm, url: e.target.value }
                                }))}
                                placeholder="https://example.com"
                                className="input"
                              />
                            </div>
                            <button
                              type="submit"
                              disabled={!siteForm.name.trim() || !siteForm.url.trim() || createSiteMutation.isPending}
                              className="btn btn-primary mt-3 flex items-center gap-2"
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
                          </form>
                          
                          {/* Sites List */}
                          {isLoadingSites ? (
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
                                        onClick={() => toggleSiteMutation.mutate({
                                          id: site.id,
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
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
