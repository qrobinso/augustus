import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation, useParams } from 'react-router-dom'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { 
  Globe,
  Loader2, 
  ArrowLeft,
  Tag
} from 'lucide-react'
import { customSitesApi, topicsApi } from '../api/client'

export default function EditSite() {
  const navigate = useNavigate()
  const location = useLocation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  
  // Fetch existing site
  const { data: existingSite, isLoading: siteLoading } = useQuery({
    queryKey: ['custom-site', id],
    queryFn: () => customSitesApi.get(id!),
    enabled: Boolean(id),
    refetchOnMount: true, // Always refetch when component mounts to get latest data
  })
  
  // Fetch topics for the topic selector
  const { data: topicsData } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  const topics = topicsData?.topics || []
  
  // Form state
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [topicId, setTopicId] = useState('')
  const [isInitialized, setIsInitialized] = useState(false)
  
  // Track what we've initialized to prevent unnecessary re-initialization
  const initializedRef = useRef<{ siteId?: string; dataHash?: string }>({})
  
  // Create a simple hash of the site data to detect changes
  const getSiteDataHash = (site: typeof existingSite) => {
    if (!site) return undefined
    return `${site.id}:${site.name}:${site.url}:${site.topic_id}`
  }
  
  // Initialize form with existing site data
  useEffect(() => {
    if (existingSite) {
      const dataHash = getSiteDataHash(existingSite)
      // Re-initialize if site ID changed OR data hash changed (data was updated)
      if (initializedRef.current.siteId !== existingSite.id || initializedRef.current.dataHash !== dataHash) {
        setName(existingSite.name)
        setUrl(existingSite.url)
        setTopicId(existingSite.topic_id)
        setIsInitialized(true)
        initializedRef.current = { siteId: existingSite.id, dataHash }
      }
    }
  }, [existingSite])
  
  const updateSiteMutation = useMutation({
    mutationFn: ({ id, ...options }: { id: string; name?: string; url?: string; topic_id?: string }) =>
      customSitesApi.update(id, options),
    onSuccess: (_, variables) => {
      // Invalidate both the list and the specific site query
      queryClient.invalidateQueries({ queryKey: ['custom-sites'] })
      queryClient.invalidateQueries({ queryKey: ['custom-site', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['topics'] }) // Update site count
      navigate(-1)
    },
  })
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name.trim()) {
      alert('Site name is required')
      return
    }
    
    if (!url.trim()) {
      alert('Site URL is required')
      return
    }
    
    if (!topicId) {
      alert('Please select a topic')
      return
    }
    
    if (id) {
      updateSiteMutation.mutate({
        id,
        name: name.trim(),
        url: url.trim(),
        topic_id: topicId,
      })
    }
  }
  
  const isLoading = updateSiteMutation.isPending
  
  // Show loading state while fetching existing site
  if (siteLoading) {
    return (
      <div className="page-container flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  // Get the previous page from location state, default to /topics
  const previousPage = (location.state as { from?: string })?.from || '/topics'
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <button
          onClick={() => navigate(previousPage)}
          className="flex items-center gap-2 text-augustus-400 hover:text-augustus-300 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </button>
        
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center">
            <Globe className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white">
              Edit Site
            </h1>
            <p className="text-sm sm:text-base text-augustus-400">
              Update your custom site settings
            </p>
          </div>
        </div>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Site Details */}
        <div className="card">
          <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
            <Globe className="w-5 h-5 text-accent" />
            Site Details
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="label">Site Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., TechCrunch, The Verge"
                className="input"
                required
                disabled={isLoading}
              />
            </div>
            
            <div>
              <label className="label">URL *</label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                className="input"
                required
                disabled={isLoading}
              />
            </div>
            
            <div>
              <label className="label">Topic *</label>
              <select
                value={topicId}
                onChange={(e) => setTopicId(e.target.value)}
                className="input"
                required
                disabled={isLoading}
              >
                <option value="">Select a topic...</option>
                {topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        
        {/* Submit Button */}
        <div className="flex flex-col-reverse sm:flex-row items-center gap-3">
          <button
            type="button"
            onClick={() => navigate(previousPage)}
            className="btn btn-ghost w-full sm:w-auto"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!name.trim() || !url.trim() || !topicId || isLoading}
            className="btn btn-primary w-full sm:w-auto flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Updating...
              </>
            ) : (
              <>
                Update Site
              </>
            )}
          </button>
        </div>
        
        {updateSiteMutation.isError && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-400">
              {(updateSiteMutation.error as Error)?.message || 'Failed to update site'}
            </p>
          </div>
        )}
      </form>
    </div>
  )
}

