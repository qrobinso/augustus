import { useState } from 'react'
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
  Check
} from 'lucide-react'
import clsx from 'clsx'
import { topicsApi, Topic } from '../api/client'

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
  const queryClient = useQueryClient()
  
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(PRESET_COLORS[0])
  const [useNewsapi, setUseNewsapi] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editColor, setEditColor] = useState('')
  const [editUseNewsapi, setEditUseNewsapi] = useState(true)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['topics'],
    queryFn: () => topicsApi.list(),
  })
  
  const createMutation = useMutation({
    mutationFn: () => topicsApi.create({ name, description: description || undefined, color, use_newsapi: useNewsapi }),
    onSuccess: () => {
      setName('')
      setDescription('')
      setUseNewsapi(true)
      // Pick next color in rotation
      const currentIndex = PRESET_COLORS.indexOf(color)
      setColor(PRESET_COLORS[(currentIndex + 1) % PRESET_COLORS.length])
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const updateMutation = useMutation({
    mutationFn: ({ id, ...options }: { id: string; name?: string; description?: string; color?: string; use_newsapi?: boolean }) =>
      topicsApi.update(id, options),
    onSuccess: () => {
      setEditingId(null)
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const deleteMutation = useMutation({
    mutationFn: (id: string) => topicsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topics'] })
    },
  })
  
  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (name.trim()) {
      createMutation.mutate()
    }
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
    updateMutation.mutate({
      id,
      name: editName,
      description: editDescription || undefined,
      color: editColor,
      use_newsapi: editUseNewsapi,
    })
  }
  
  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
          Topics
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Manage your news topics and categories for briefings
        </p>
      </div>
      
      {/* Add new topic form */}
      <form onSubmit={handleCreate} className="card mb-6 sm:mb-8">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Tag className="w-5 h-5 text-accent" />
          Add New Topic
        </h2>
        
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="label">Topic Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Artificial Intelligence, Climate Change"
                className="input"
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
          
          <button
            type="submit"
            disabled={!name.trim() || createMutation.isPending}
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
                Add Topic
              </>
            )}
          </button>
          
          {createMutation.isError && (
            <p className="text-sm text-red-400">
              {(createMutation.error as Error)?.message || 'Failed to add topic'}
            </p>
          )}
        </div>
      </form>
      
      {/* Topics list */}
      <div className="space-y-4">
        <h2 className="text-base sm:text-lg font-semibold text-white">Your Topics</h2>
        
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
            {data?.topics.map((topic) => (
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
                        disabled={updateMutation.isPending}
                        className="btn btn-primary flex-1 flex items-center justify-center gap-1"
                      >
                        {updateMutation.isPending ? (
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
                    <div className="flex items-start gap-3">
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
                          {!topic.use_newsapi && (
                            <span className="text-augustus-600">• Custom sites only</span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2 mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-augustus-800/50">
                      <button
                        onClick={() => startEdit(topic)}
                        className="btn btn-ghost p-2 text-augustus-400 hover:text-white"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (topic.site_count > 0) {
                            if (!confirm(`This will also delete ${topic.site_count} custom site(s) linked to this topic. Continue?`)) {
                              return
                            }
                          }
                          deleteMutation.mutate(topic.id)
                        }}
                        className="btn btn-ghost p-2 text-augustus-500 hover:text-red-400"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}


