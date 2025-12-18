import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Globe, 
  Loader2, 
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle,
  XCircle,
  ExternalLink,
  Play,
  Pause,
  RefreshCw,
  Tag
} from 'lucide-react'
import clsx from 'clsx'
import { customSitesApi, topicsApi, CustomSite, Topic } from '../api/client'

export default function CustomSites() {
  const queryClient = useQueryClient()
  
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [topicId, setTopicId] = useState<string>('')
  const [filterTopicId, setFilterTopicId] = useState<string>('')
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{
    siteId: string
    success: boolean
    message: string
    articles?: Array<{ title: string; url: string }>
  } | null>(null)
  
  // Fetch topics for dropdown and filter
  const { data: topicsData } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  const topics = topicsData?.topics || []
  
  // Set default topic when topics load
  if (topics.length > 0 && !topicId) {
    setTopicId(topics[0].id)
  }
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['custom-sites', filterTopicId],
    queryFn: () => customSitesApi.list(filterTopicId || undefined),
  })
  
  const createMutation = useMutation({
    mutationFn: () => customSitesApi.create({ name, url, topic_id: topicId }),
    onSuccess: () => {
      setName('')
      setUrl('')
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      queryClient.invalidateQueries({ queryKey: ['topics'] }) // Update site counts
    },
  })
  
  const deleteMutation = useMutation({
    mutationFn: (id: string) => customSitesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      queryClient.invalidateQueries({ queryKey: ['topics'] }) // Update site counts
    },
  })
  
  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      customSitesApi.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
    },
  })
  
  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (name.trim() && url.trim() && topicId) {
      createMutation.mutate()
    }
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
      // Refresh to get updated last_fetched
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
  
  const getTopicStyle = (color?: string) => {
    const c = color || '#3B82F6'
    return {
      backgroundColor: `${c}20`,
      color: c,
    }
  }
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          Custom Sites
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Add your favorite websites and blogs to include in daily briefings
        </p>
      </div>
      
      {/* Add new site form */}
      <form onSubmit={handleCreate} className="card mb-6 sm:mb-8">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5 text-accent" />
          Add New Site
        </h2>
        
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Site Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., TechCrunch, The Verge"
                className="input"
              />
            </div>
            
            <div>
              <label className="label">Topic</label>
              <select
                value={topicId}
                onChange={(e) => setTopicId(e.target.value)}
                className="input"
                disabled={topics.length === 0}
              >
                {topics.length === 0 ? (
                  <option value="">No topics available</option>
                ) : (
                  topics.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.name}
                    </option>
                  ))
                )}
              </select>
              {topics.length === 0 && (
                <p className="text-xs text-augustus-500 mt-1">
                  Create topics first in the Topics page
                </p>
              )}
            </div>
          </div>
          
          <div>
            <label className="label">Website URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="input"
            />
            <p className="text-xs text-augustus-500 mt-1">
              Enter the main page or news/blog section URL
            </p>
          </div>
          
          <button
            type="submit"
            disabled={!name.trim() || !url.trim() || !topicId || createMutation.isPending}
            className="btn btn-primary w-full sm:w-auto flex items-center justify-center gap-2"
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Adding...
              </>
            ) : (
              <>
                <Plus className="w-5 h-5" />
                Add Site
              </>
            )}
          </button>
          
          {createMutation.isError && (
            <p className="text-sm text-red-400">
              {(createMutation.error as Error)?.message || 'Failed to add site'}
            </p>
          )}
        </div>
      </form>
      
      {/* Filter */}
      <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-2">
        <span className="text-xs sm:text-sm text-augustus-400 flex-shrink-0">Filter:</span>
        <div className="flex flex-wrap gap-1.5 sm:gap-2">
          <button
            onClick={() => setFilterTopicId('')}
            className={clsx(
              'px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all whitespace-nowrap min-h-[32px]',
              filterTopicId === ''
                ? 'bg-accent text-white'
                : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
            )}
          >
            All
          </button>
          {topics.map((topic) => (
            <button
              key={topic.id}
              onClick={() => setFilterTopicId(topic.id)}
              className={clsx(
                'px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all flex items-center gap-1 whitespace-nowrap min-h-[32px]',
                filterTopicId === topic.id
                  ? 'bg-accent text-white'
                  : 'bg-augustus-800 text-augustus-300 hover:bg-augustus-700 active:bg-augustus-600'
              )}
            >
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: topic.color || '#3B82F6' }}
              />
              {topic.name}
            </button>
          ))}
        </div>
      </div>
      
      {/* Sites list */}
      <div className="space-y-3 sm:space-y-4">
        {isLoading ? (
          <div className="card flex items-center justify-center py-10 sm:py-12">
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="card text-center py-10 sm:py-12">
            <AlertCircle className="w-10 sm:w-12 h-10 sm:h-12 text-red-500 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">Failed to load sites. Is the backend running?</p>
          </div>
        ) : data?.sites.length === 0 ? (
          <div className="card text-center py-10 sm:py-12">
            <Globe className="w-10 sm:w-12 h-10 sm:h-12 text-augustus-600 mx-auto mb-3 sm:mb-4" />
            <p className="text-sm sm:text-base text-augustus-400">
              {filterTopicId 
                ? `No sites in this topic. Add your first one!`
                : 'No custom sites yet. Add your first one!'}
            </p>
          </div>
        ) : (
          data?.sites.map((site) => (
            <div
              key={site.id}
              className="card hover:border-augustus-700 transition-colors"
            >
              <div className="flex items-center gap-3 sm:gap-4">
                {/* Status indicator */}
                <div
                  className={clsx(
                    'w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center flex-shrink-0',
                    site.is_active
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-augustus-800 text-augustus-500'
                  )}
                >
                  <Globe className="w-5 h-5 sm:w-6 sm:h-6" />
                </div>
                
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-white text-sm sm:text-base">{site.name}</h3>
                    <span 
                      className="px-1.5 sm:px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1"
                      style={getTopicStyle(site.topic_color)}
                    >
                      <Tag className="w-3 h-3" />
                      {site.topic_name || 'Unknown'}
                    </span>
                  </div>
                  <a
                    href={site.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs sm:text-sm text-augustus-400 hover:text-accent truncate flex items-center gap-1"
                  >
                    <span className="truncate">{site.url}</span>
                    <ExternalLink className="w-3 h-3 flex-shrink-0" />
                  </a>
                  <div className="flex items-center gap-3 sm:gap-4 text-xs text-augustus-500 mt-1">
                    <span className="hidden sm:inline">Last: {formatDate(site.last_fetched)}</span>
                    {site.last_error && (
                      <span className="text-red-400 flex items-center gap-1">
                        <XCircle className="w-3 h-3" />
                        Error
                      </span>
                    )}
                  </div>
                </div>
                
                {/* Actions */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleTest(site)}
                    disabled={testingId === site.id}
                    className="btn btn-ghost p-2"
                    title="Test fetch"
                  >
                    {testingId === site.id ? (
                      <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4 sm:w-5 sm:h-5" />
                    )}
                  </button>
                  
                  <button
                    onClick={() => toggleMutation.mutate({
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
                      <Pause className="w-4 h-4 sm:w-5 sm:h-5" />
                    ) : (
                      <Play className="w-4 h-4 sm:w-5 sm:h-5" />
                    )}
                  </button>
                  
                  <button
                    onClick={() => deleteMutation.mutate(site.id)}
                    className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4 sm:w-5 sm:h-5" />
                  </button>
                </div>
              </div>
              
              {/* Test result */}
              {testResult && testResult.siteId === site.id && (
                <div className={clsx(
                  'mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-augustus-800/50',
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
                          className="text-xs sm:text-sm text-augustus-400 hover:text-accent block truncate"
                        >
                          • {article.title}
                        </a>
                      ))}
                      {testResult.articles.length > 3 && (
                        <span className="text-xs sm:text-sm text-augustus-500">
                          ...and {testResult.articles.length - 3} more
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
