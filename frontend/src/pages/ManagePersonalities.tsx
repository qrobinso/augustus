import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  ArrowLeft,
  Loader2, 
  FileText,
  Save,
  Plus,
  X,
  AlertCircle,
  CheckCircle,
  Trash2
} from 'lucide-react'
import clsx from 'clsx'
import { castsApi } from '../api/client'

interface PersonalityFile {
  filename: string
  name: string
  path: string
}

export default function ManagePersonalities() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<string>('')
  const [isEditing, setIsEditing] = useState(false)
  const [newFileName, setNewFileName] = useState('')
  const [showNewFileForm, setShowNewFileForm] = useState(false)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  
  const { data: files, isLoading: isLoadingFiles } = useQuery({
    queryKey: ['personality-files'],
    queryFn: () => castsApi.listPersonalityFiles(),
  })
  
  const { data: currentFile, isLoading: isLoadingFile } = useQuery({
    queryKey: ['personality-file', selectedFile],
    queryFn: () => castsApi.getPersonalityFile(selectedFile!),
    enabled: !!selectedFile && !isEditing,
  })
  
  const saveMutation = useMutation({
    mutationFn: ({ filename, content }: { filename: string; content: string }) =>
      castsApi.savePersonalityFile(filename, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personality-file', selectedFile] })
      queryClient.invalidateQueries({ queryKey: ['personality-files'] })
      queryClient.invalidateQueries({ queryKey: ['personalities'] })
      setHasUnsavedChanges(false)
      setIsEditing(false)
    },
  })
  
  const createMutation = useMutation({
    mutationFn: ({ filename, content }: { filename: string; content?: string }) =>
      castsApi.createPersonalityFile(filename, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personality-files'] })
      queryClient.invalidateQueries({ queryKey: ['personalities'] })
      setShowNewFileForm(false)
      setNewFileName('')
    },
  })
  
  const deleteMutation = useMutation({
    mutationFn: (filename: string) => castsApi.deletePersonalityFile(filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personality-files'] })
      queryClient.invalidateQueries({ queryKey: ['personalities'] })
      if (selectedFile) {
        setSelectedFile(null)
        setFileContent('')
        setIsEditing(false)
        setHasUnsavedChanges(false)
      }
    },
  })
  
  const handleFileSelect = (filename: string) => {
    if (hasUnsavedChanges) {
      if (!confirm('You have unsaved changes. Discard them?')) {
        return
      }
    }
    setSelectedFile(filename)
    setIsEditing(false)
    setHasUnsavedChanges(false)
  }
  
  const handleEdit = () => {
    if (currentFile) {
      setFileContent(currentFile.content)
      setIsEditing(true)
    }
  }
  
  const handleSave = () => {
    if (selectedFile && fileContent.trim()) {
      saveMutation.mutate({ filename: selectedFile, content: fileContent })
    }
  }
  
  const handleContentChange = (content: string) => {
    setFileContent(content)
    setHasUnsavedChanges(true)
  }
  
  const handleCreateFile = () => {
    if (!newFileName.trim()) {
      alert('Please enter a filename')
      return
    }
    createMutation.mutate({ filename: newFileName.trim() })
  }
  
  // Update file content when currentFile changes
  useEffect(() => {
    if (currentFile && !isEditing) {
      setFileContent(currentFile.content)
    }
  }, [currentFile, isEditing])
  
  if (isLoadingFiles) {
    return (
      <div className="page-container flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    )
  }
  
  return (
    <div className="page-container max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/casts')}
          className="btn btn-ghost flex items-center gap-2"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2">
            Manage Personalities
          </h1>
          <p className="text-sm sm:text-base text-augustus-400">
            Browse, edit, and create personality files
          </p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* File Browser Sidebar */}
        <div className="lg:col-span-1">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">Personality Files</h2>
              <button
                onClick={() => setShowNewFileForm(!showNewFileForm)}
                className="btn-icon btn btn-ghost btn-sm"
                title="Create new file"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            
            {/* New File Form */}
            {showNewFileForm && (
              <div className="mb-4 p-3 bg-augustus-900/50 rounded-lg">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newFileName}
                    onChange={(e) => setNewFileName(e.target.value)}
                    placeholder="filename.py"
                    className="flex-1 input input-sm"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleCreateFile()
                      } else if (e.key === 'Escape') {
                        setShowNewFileForm(false)
                        setNewFileName('')
                      }
                    }}
                    autoFocus
                  />
                  <button
                    onClick={handleCreateFile}
                    disabled={createMutation.isPending || !newFileName.trim()}
                    className="btn btn-sm btn-primary"
                  >
                    {createMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Plus className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setShowNewFileForm(false)
                      setNewFileName('')
                    }}
                    className="btn btn-sm btn-ghost"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
            
            {/* File List */}
            <div className="space-y-1 max-h-[60vh] overflow-y-auto">
              {files?.map((file) => (
                <div
                  key={file.filename}
                  className={clsx(
                    'group flex items-center gap-2 p-3 rounded-lg transition-colors',
                    selectedFile === file.filename
                      ? 'bg-accent/20 border border-accent/30'
                      : 'bg-augustus-900/50 hover:bg-augustus-800/50'
                  )}
                >
                  <button
                    onClick={() => handleFileSelect(file.filename)}
                    className="flex-1 text-left min-w-0"
                  >
                    <div className="flex items-center gap-2">
                      <FileText className={clsx(
                        'w-4 h-4 flex-shrink-0',
                        selectedFile === file.filename ? 'text-accent' : 'text-augustus-400'
                      )} />
                      <span className={clsx(
                        'text-sm font-medium truncate',
                        selectedFile === file.filename ? 'text-accent' : 'text-augustus-300'
                      )}>
                        {file.name}
                      </span>
                    </div>
                    <div className="text-xs text-augustus-500 mt-1 truncate">{file.filename}</div>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (confirm(`Delete "${file.filename}"? This action cannot be undone.`)) {
                        deleteMutation.mutate(file.filename)
                      }
                    }}
                    disabled={deleteMutation.isPending}
                    className="btn-icon btn btn-ghost btn-sm opacity-0 group-hover:opacity-100 transition-opacity text-red-400 hover:text-red-300"
                    title="Delete file"
                  >
                    {deleteMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Editor */}
        <div className="lg:col-span-2">
          {selectedFile ? (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-white">{selectedFile}</h2>
                  {hasUnsavedChanges && (
                    <p className="text-xs text-yellow-400 mt-1">Unsaved changes</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {!isEditing ? (
                    <button
                      onClick={handleEdit}
                      className="btn btn-sm btn-primary"
                    >
                      Edit
                    </button>
                  ) : (
                    <>
                      <button
                        onClick={() => {
                          if (hasUnsavedChanges && !confirm('Discard changes?')) {
                            return
                          }
                          setIsEditing(false)
                          setHasUnsavedChanges(false)
                          if (currentFile) {
                            setFileContent(currentFile.content)
                          }
                        }}
                        className="btn btn-sm btn-ghost"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={saveMutation.isPending || !fileContent.trim()}
                        className="btn btn-sm btn-primary flex items-center gap-2"
                      >
                        {saveMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Save className="w-4 h-4" />
                        )}
                        Save
                      </button>
                    </>
                  )}
                </div>
              </div>
              
              {isLoadingFile ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-accent" />
                </div>
              ) : (
                <div className="relative">
                  <textarea
                    value={fileContent}
                    onChange={(e) => handleContentChange(e.target.value)}
                    disabled={!isEditing}
                    className={clsx(
                      'w-full h-[60vh] font-mono text-sm p-4 rounded-lg',
                      'bg-augustus-900/50 text-augustus-200',
                      'border border-augustus-700',
                      'focus:outline-none focus:ring-2 focus:ring-accent/50',
                      !isEditing && 'opacity-60 cursor-not-allowed'
                    )}
                    spellCheck={false}
                  />
                </div>
              )}
              
              {saveMutation.isError && (
                <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4" />
                  {saveMutation.error instanceof Error 
                    ? saveMutation.error.message 
                    : 'Failed to save file'}
                </div>
              )}
              
              {saveMutation.isSuccess && (
                <div className="mt-4 p-3 bg-green-500/10 border border-green-500/20 rounded-lg flex items-center gap-2 text-green-400 text-sm">
                  <CheckCircle className="w-4 h-4" />
                  File saved successfully
                </div>
              )}
            </div>
          ) : (
            <div className="card flex items-center justify-center py-20">
              <div className="text-center">
                <FileText className="w-12 h-12 text-augustus-600 mx-auto mb-4" />
                <p className="text-augustus-400">Select a file to view or edit</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

