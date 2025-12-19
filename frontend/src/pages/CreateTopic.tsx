import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Tag,
  Loader2, 
  Plus,
  AlertCircle,
  X,
  Sparkles,
  ArrowLeft
} from 'lucide-react'
import clsx from 'clsx'
import { topicsApi, customSitesApi } from '../api/client'

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

export default function CreateTopic() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  // Topic form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(() => PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)])
  const [useNewsapi, setUseNewsapi] = useState(true)
  
  // Site management state
  const [pendingSites, setPendingSites] = useState<PendingSite[]>([])
  const [siteForm, setSiteForm] = useState({ name: '', url: '' })
  
  // AI site generation state
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedSites, setGeneratedSites] = useState<GeneratedSite[]>([])
  const [selectedGeneratedSites, setSelectedGeneratedSites] = useState<Set<number>>(new Set())
  const [showGeneratedSites, setShowGeneratedSites] = useState(false)
  
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
      navigate('/topics')
    },
  })
  
  const [tempTopicId, setTempTopicId] = useState<string | null>(null)
  
  const handleGenerateSites = async () => {
    if (!name.trim()) {
      alert('Please enter a topic name first')
      return
    }
    
    setIsGenerating(true)
    try {
      // Create a temporary topic to generate sites
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
    } catch (error) {
      console.error('Failed to generate sites:', error)
      alert('Failed to generate site suggestions')
    } finally {
      setIsGenerating(false)
    }
  }
  
  const handleAddSelectedGeneratedSites = () => {
    const sitesToAdd = Array.from(selectedGeneratedSites).map(i => generatedSites[i])
    setPendingSites(prev => [...prev, ...sitesToAdd])
    setShowGeneratedSites(false)
    setGeneratedSites([])
    setSelectedGeneratedSites(new Set())
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
      setPendingSites(prev => [...prev, { ...siteForm }])
      setSiteForm({ name: '', url: '' })
    }
  }
  
  const handleRemovePendingSite = (index: number) => {
    setPendingSites(prev => prev.filter((_, i) => i !== index))
  }
  
  const handleCreateTopic = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    createTopicMutation.mutate()
  }
  
  const handleCancel = () => {
    // If we have a temp topic, delete it
    if (tempTopicId) {
      topicsApi.delete(tempTopicId).catch(console.error)
    }
    navigate('/topics')
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
          <span className="text-sm">Back to Topics</span>
        </button>
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          Create New Topic
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Create a new topic and add sites in one go
        </p>
      </div>
      
      <form onSubmit={handleCreateTopic} className="space-y-6">
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
              />
            </div>
            
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="use-newsapi"
                checked={useNewsapi}
                onChange={(e) => setUseNewsapi(e.target.checked)}
                className="w-5 h-5 rounded border-augustus-700 bg-augustus-900 text-accent focus:ring-accent focus:ring-2"
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
              disabled={isGenerating || !name.trim()}
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
                    disabled={selectedGeneratedSites.size === 0}
                    className="btn btn-primary flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    Add Selected ({selectedGeneratedSites.size})
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
          
          <form onSubmit={handleAddManualSite} className="space-y-3">
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
              type="submit"
              disabled={!siteForm.name.trim() || !siteForm.url.trim()}
              className="btn btn-secondary flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Site
            </button>
          </form>
        </div>
        
        {/* Pending Sites List */}
        {pendingSites.length > 0 && (
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
        
        {/* Create Button */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={!name.trim() || createTopicMutation.isPending}
            className="btn btn-primary flex items-center justify-center gap-2"
          >
            {createTopicMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-5 h-5" />
                Create Topic
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleCancel}
            className="btn btn-ghost"
          >
            Cancel
          </button>
        </div>
        
        {createTopicMutation.isError && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-400">
              {(createTopicMutation.error as Error)?.message || 'Failed to create topic'}
            </p>
          </div>
        )}
      </form>
    </div>
  )
}

