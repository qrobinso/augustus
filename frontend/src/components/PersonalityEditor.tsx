import { useState, useEffect, useRef, useCallback } from 'react'
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
  Trash2,
} from 'lucide-react'
import clsx from 'clsx'
import { castsApi } from '../api/client'
import {
  PersonalityChange,
  findPersonalityFile,
  parsePersonalityName,
  personalityErrorMessage,
  validatePersonalityFilename,
} from './personalityFiles'

export type { PersonalityChange } from './personalityFiles'

interface PersonalityEditorProps {
  open: boolean
  onClose: () => void
  /** Personality display name whose file should be opened on launch. */
  personality?: string | null
  /** 'create' opens with the new-personality form showing. */
  mode?: 'browse' | 'create'
  /**
   * Called after a personality file is created, saved, or deleted, once the
   * `['personalities']` query has been refetched (its fresh list is included).
   */
  onChange?: (change: PersonalityChange) => void
}

type PersonalityFile = { filename: string; name: string; content: string }
type Notice = { tone: 'success' | 'warning'; text: string }

/**
 * Personality file browser/editor presented as a full-height bottom sheet
 * on mobile and a centered two-pane dialog on desktop.
 */
export default function PersonalityEditor(props: PersonalityEditorProps) {
  if (!props.open) return null
  return <PersonalityEditorPanel {...props} />
}

function PersonalityEditorPanel({
  onClose,
  personality = null,
  mode = 'browse',
  onChange,
}: PersonalityEditorProps) {
  const queryClient = useQueryClient()
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<string>('')
  const [isEditing, setIsEditing] = useState(false)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [showNewFileForm, setShowNewFileForm] = useState(mode === 'create')
  const [newFileName, setNewFileName] = useState('')
  const [newFileError, setNewFileError] = useState<string | null>(null)
  const [resolving, setResolving] = useState(Boolean(personality) && mode !== 'create')
  const [resolveMiss, setResolveMiss] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const resolvedRef = useRef(false)

  const {
    data: files,
    isLoading: isLoadingFiles,
    error: filesError,
  } = useQuery({
    queryKey: ['personality-files'],
    queryFn: () => castsApi.listPersonalityFiles(),
  })

  const {
    data: currentFile,
    isLoading: isLoadingFile,
    error: fileError,
  } = useQuery({
    queryKey: ['personality-file', selectedFile],
    queryFn: () => castsApi.getPersonalityFile(selectedFile!),
    enabled: !!selectedFile && !isEditing,
  })

  const readFile = useCallback(
    (filename: string) =>
      queryClient.fetchQuery({
        queryKey: ['personality-file', filename],
        queryFn: () => castsApi.getPersonalityFile(filename),
        staleTime: 30_000,
      }),
    [queryClient],
  )

  /** Refetch the selectable personality list (shared with the cast form). */
  const refreshPersonalities = useCallback(async (): Promise<string[]> => {
    try {
      return await queryClient.fetchQuery({
        queryKey: ['personalities'],
        queryFn: () => castsApi.getPersonalities(),
        staleTime: 0,
      })
    } catch {
      return queryClient.getQueryData<string[]>(['personalities']) ?? []
    }
  }, [queryClient])

  // Open the requested personality's file once the file list is known.
  // Runs until it completes once; a manual selection also marks it done.
  useEffect(() => {
    if (resolvedRef.current || !files || !personality || mode === 'create') return
    let cancelled = false
    findPersonalityFile(personality, files.map((f) => f.filename), readFile).then((filename) => {
      if (cancelled || resolvedRef.current) return
      resolvedRef.current = true
      if (filename) setSelectedFile(filename)
      else setResolveMiss(personality)
      setResolving(false)
    })
    return () => {
      cancelled = true
    }
  }, [files, personality, mode, readFile])

  // A failed file list means resolution can never finish.
  useEffect(() => {
    if (filesError) {
      resolvedRef.current = true
      setResolving(false)
    }
  }, [filesError])

  // Update file content when currentFile changes
  useEffect(() => {
    if (currentFile && !isEditing) {
      setFileContent(currentFile.content)
    }
  }, [currentFile, isEditing])

  const saveMutation = useMutation({
    mutationFn: ({ filename, content }: { filename: string; content: string; previousName: string | null }) =>
      castsApi.savePersonalityFile(filename, content),
    onSuccess: async (result, { filename, content, previousName }) => {
      queryClient.setQueryData<PersonalityFile>(['personality-file', filename], {
        filename,
        name: result.name,
        content,
      })
      queryClient.invalidateQueries({ queryKey: ['personality-file', filename] })
      queryClient.invalidateQueries({ queryKey: ['personality-files'] })
      setHasUnsavedChanges(false)
      setIsEditing(false)
      const available = await refreshPersonalities()
      const name = parsePersonalityName(content)
      setNotice(loadNotice('File saved successfully', name, available))
      onChange?.({ type: 'saved', filename, previousName, name, available })
    },
  })

  const createMutation = useMutation({
    mutationFn: async (filename: string) => {
      const created = await castsApi.createPersonalityFile(filename)
      return castsApi.getPersonalityFile(created.filename)
    },
    onSuccess: async (file) => {
      queryClient.setQueryData<PersonalityFile>(['personality-file', file.filename], file)
      queryClient.invalidateQueries({ queryKey: ['personality-files'] })
      setShowNewFileForm(false)
      setNewFileName('')
      setNewFileError(null)
      // Open the template straight into edit mode so it can be filled in.
      setSelectedFile(file.filename)
      setFileContent(file.content)
      setIsEditing(true)
      setHasUnsavedChanges(false)
      setResolveMiss(null)
      const available = await refreshPersonalities()
      const name = parsePersonalityName(file.content)
      setNotice(loadNotice(`Created ${file.filename}. Fill in the template and save.`, name, available))
      onChange?.({ type: 'created', filename: file.filename, previousName: null, name, available })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (filename: string) => {
      const cached = queryClient.getQueryData<PersonalityFile>(['personality-file', filename])
      await castsApi.deletePersonalityFile(filename)
      return cached ? parsePersonalityName(cached.content) : null
    },
    onSuccess: async (previousName, filename) => {
      queryClient.removeQueries({ queryKey: ['personality-file', filename] })
      queryClient.invalidateQueries({ queryKey: ['personality-files'] })
      if (selectedFile === filename) {
        setSelectedFile(null)
        setFileContent('')
        setIsEditing(false)
        setHasUnsavedChanges(false)
        setNotice(null)
      }
      const available = await refreshPersonalities()
      onChange?.({ type: 'deleted', filename, previousName, name: null, available })
    },
  })

  const confirmDiscard = (message = 'You have unsaved changes. Discard them?') =>
    !hasUnsavedChanges || confirm(message)

  const requestClose = () => {
    if (confirmDiscard()) onClose()
  }

  // Escape closes; lock background scroll while open.
  const requestCloseRef = useRef(requestClose)
  requestCloseRef.current = requestClose
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') requestCloseRef.current()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [])

  const stopResolving = () => {
    resolvedRef.current = true
    setResolving(false)
  }

  const handleFileSelect = (filename: string) => {
    if (!confirmDiscard()) return
    stopResolving()
    setSelectedFile(filename)
    setIsEditing(false)
    setHasUnsavedChanges(false)
    setNotice(null)
    saveMutation.reset()
  }

  const handleBackToList = () => {
    if (!confirmDiscard()) return
    setSelectedFile(null)
    setIsEditing(false)
    setHasUnsavedChanges(false)
    setNotice(null)
    stopResolving()
  }

  const handleEdit = () => {
    if (currentFile) {
      setFileContent(currentFile.content)
      setIsEditing(true)
      setNotice(null)
      saveMutation.reset()
    }
  }

  const handleCancelEdit = () => {
    if (!confirmDiscard('Discard changes?')) return
    setIsEditing(false)
    setHasUnsavedChanges(false)
    const cached = selectedFile
      ? queryClient.getQueryData<PersonalityFile>(['personality-file', selectedFile])
      : undefined
    if (cached) setFileContent(cached.content)
  }

  const handleSave = () => {
    if (selectedFile && fileContent.trim()) {
      const cached = queryClient.getQueryData<PersonalityFile>(['personality-file', selectedFile])
      saveMutation.mutate({
        filename: selectedFile,
        content: fileContent,
        previousName: cached ? parsePersonalityName(cached.content) : null,
      })
    }
  }

  const handleContentChange = (content: string) => {
    setFileContent(content)
    setHasUnsavedChanges(true)
  }

  const closeNewFileForm = () => {
    setShowNewFileForm(false)
    setNewFileName('')
    setNewFileError(null)
    createMutation.reset()
  }

  const handleCreateFile = () => {
    const result = validatePersonalityFilename(newFileName, files?.map((f) => f.filename) ?? [])
    if (result.error !== null) {
      setNewFileError(result.error)
      return
    }
    if (!confirmDiscard()) return
    setNewFileError(null)
    stopResolving()
    createMutation.mutate(result.filename)
  }

  const showDetailOnMobile = Boolean(selectedFile) || resolving
  const declaredName = parsePersonalityName(fileContent)

  return (
    <div
      className="fixed inset-0 z-[60]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="personality-editor-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in"
        onClick={requestClose}
      />

      {/* Panel: full-height bottom sheet on mobile, centered dialog on sm+ */}
      <div className="absolute inset-x-0 bottom-0 sm:inset-0 sm:flex sm:items-center sm:justify-center sm:p-6 pointer-events-none">
        <div className="pointer-events-auto bg-augustus-900 border-t sm:border border-augustus-700/60 rounded-t-3xl sm:rounded-2xl shadow-2xl shadow-black/60 w-full sm:max-w-5xl h-[92dvh] sm:h-[85dvh] flex flex-col overscroll-contain pb-safe animate-sheet-up">
          {/* Grab handle (mobile) + header */}
          <div className="flex-shrink-0">
            <div className="sm:hidden flex justify-center pt-3">
              <div className="w-10 h-1 rounded-full bg-augustus-700" />
            </div>
            <div className="flex items-center justify-between gap-3 px-4 sm:px-6 pt-2 sm:pt-4 pb-3">
              <div className="min-w-0">
                <h2 id="personality-editor-title" className="text-lg sm:text-xl font-display font-semibold text-white">
                  Personalities
                </h2>
                <p className="text-xs sm:text-sm text-augustus-400">
                  Browse, edit, and create personality files
                </p>
              </div>
              <button
                type="button"
                onClick={requestClose}
                className="btn btn-ghost p-2 min-h-[44px] min-w-[44px] text-augustus-400 hover:text-white"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="flex-1 min-h-0 grid grid-cols-1 sm:grid-cols-3 gap-4 px-4 sm:px-6 pb-4">
            {/* File list */}
            <div className={clsx('sm:col-span-1 min-h-0 flex-col', showDetailOnMobile ? 'hidden sm:flex' : 'flex')}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-augustus-300">Personality Files</h3>
                <button
                  type="button"
                  onClick={() => (showNewFileForm ? closeNewFileForm() : setShowNewFileForm(true))}
                  className="btn btn-ghost btn-sm flex items-center gap-1.5"
                  title="Create new personality"
                >
                  <Plus className="w-4 h-4" />
                  New
                </button>
              </div>

              {/* New File Form */}
              {showNewFileForm && (
                <div className="mb-3 p-3 bg-augustus-800/50 border border-augustus-700 rounded-lg">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newFileName}
                      onChange={(e) => {
                        setNewFileName(e.target.value)
                        setNewFileError(null)
                      }}
                      placeholder="filename.py"
                      aria-label="New personality filename"
                      className="flex-1 min-w-0 input input-sm"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          handleCreateFile()
                        } else if (e.key === 'Escape') {
                          // Close just the form, not the whole sheet.
                          e.stopPropagation()
                          closeNewFileForm()
                        }
                      }}
                      autoFocus
                      autoCapitalize="off"
                      autoCorrect="off"
                      spellCheck={false}
                    />
                    <button
                      type="button"
                      onClick={handleCreateFile}
                      disabled={createMutation.isPending || !newFileName.trim()}
                      className="btn btn-sm btn-primary"
                      aria-label="Create personality"
                    >
                      {createMutation.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Plus className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={closeNewFileForm}
                      className="btn btn-sm btn-ghost"
                      aria-label="Cancel new personality"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  {(newFileError || createMutation.isError) && (
                    <p className="mt-2 text-xs text-red-400 flex items-start gap-1.5">
                      <AlertCircle className="w-3.5 h-3.5 mt-px flex-shrink-0" />
                      {newFileError ?? personalityErrorMessage(createMutation.error, 'Failed to create file')}
                    </p>
                  )}
                  {!newFileError && !createMutation.isError && (
                    <p className="mt-2 text-xs text-augustus-500">
                      Starts from a template you can edit.
                    </p>
                  )}
                </div>
              )}

              {/* File List */}
              <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain space-y-1">
                {isLoadingFiles ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-accent" />
                  </div>
                ) : filesError ? (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {personalityErrorMessage(filesError, 'Failed to load personality files')}
                  </div>
                ) : files && files.length === 0 ? (
                  <p className="text-sm text-augustus-500 py-6 text-center">No personality files yet</p>
                ) : (
                  files?.map((file) => {
                    const isSelected = selectedFile === file.filename
                    const isDeleting = deleteMutation.isPending && deleteMutation.variables === file.filename
                    return (
                      <div
                        key={file.filename}
                        className={clsx(
                          'group flex items-center gap-2 p-3 rounded-lg transition-colors',
                          isSelected
                            ? 'bg-accent/20 border border-accent/30'
                            : 'bg-augustus-800/50 hover:bg-augustus-800 border border-transparent'
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => handleFileSelect(file.filename)}
                          className="flex-1 text-left min-w-0"
                        >
                          <div className="flex items-center gap-2">
                            <FileText className={clsx(
                              'w-4 h-4 flex-shrink-0',
                              isSelected ? 'text-accent' : 'text-augustus-400'
                            )} />
                            <span className={clsx(
                              'text-sm font-medium truncate',
                              isSelected ? 'text-accent' : 'text-augustus-300'
                            )}>
                              {file.name}
                            </span>
                          </div>
                          <div className="text-xs text-augustus-500 mt-1 truncate">{file.filename}</div>
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            if (confirm(`Delete "${file.filename}"? This action cannot be undone.`)) {
                              deleteMutation.mutate(file.filename)
                            }
                          }}
                          disabled={deleteMutation.isPending}
                          className="btn-icon btn btn-ghost btn-sm sm:opacity-0 sm:group-hover:opacity-100 focus-visible:opacity-100 transition-opacity text-red-400 hover:text-red-300"
                          title="Delete file"
                          aria-label={`Delete ${file.filename}`}
                        >
                          {isDeleting ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    )
                  })
                )}
              </div>

              {deleteMutation.isError && (
                <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {personalityErrorMessage(deleteMutation.error, 'Failed to delete file')}
                </div>
              )}
            </div>

            {/* Editor */}
            <div className={clsx('sm:col-span-2 min-h-0 flex-col', showDetailOnMobile ? 'flex' : 'hidden sm:flex')}>
              {resolving ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-augustus-400 text-sm">
                  <Loader2 className="w-8 h-8 animate-spin text-accent" />
                  Opening {personality}…
                </div>
              ) : selectedFile ? (
                <>
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div className="min-w-0 flex items-center gap-1">
                      <button
                        type="button"
                        onClick={handleBackToList}
                        className="sm:hidden btn btn-ghost p-2 -ml-2 min-h-[44px] min-w-[44px] text-augustus-400 hover:text-white"
                        aria-label="Back to personality files"
                      >
                        <ArrowLeft className="w-5 h-5" />
                      </button>
                      <div className="min-w-0">
                        <h3 className="text-base sm:text-lg font-semibold text-white truncate">{selectedFile}</h3>
                        <p className="text-xs text-augustus-500 truncate">
                          {declaredName ? <>Personality: <span className="text-augustus-300">{declaredName}</span></> : 'No name property found'}
                          {hasUnsavedChanges && <span className="text-yellow-400"> · Unsaved changes</span>}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {!isEditing ? (
                        <button
                          type="button"
                          onClick={handleEdit}
                          disabled={!currentFile}
                          className="btn btn-sm btn-primary"
                        >
                          Edit
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={handleCancelEdit}
                            className="btn btn-sm btn-ghost"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
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

                  {isLoadingFile && !isEditing ? (
                    <div className="flex-1 flex items-center justify-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin text-accent" />
                    </div>
                  ) : fileError && !currentFile ? (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      {personalityErrorMessage(fileError, 'Failed to load file')}
                    </div>
                  ) : (
                    <textarea
                      value={fileContent}
                      onChange={(e) => handleContentChange(e.target.value)}
                      readOnly={!isEditing}
                      aria-label={`Contents of ${selectedFile}`}
                      className={clsx(
                        'flex-1 min-h-[12rem] w-full resize-none font-mono text-sm p-4 rounded-lg',
                        'bg-augustus-800/50 text-augustus-200',
                        'border border-augustus-700',
                        'focus:outline-none focus:ring-2 focus:ring-accent/50',
                        !isEditing && 'opacity-60'
                      )}
                      spellCheck={false}
                    />
                  )}

                  {saveMutation.isError && (
                    <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      {personalityErrorMessage(saveMutation.error, 'Failed to save file')}
                    </div>
                  )}

                  {notice && !saveMutation.isError && (
                    <div className={clsx(
                      'mt-3 p-3 rounded-lg flex items-center gap-2 text-sm',
                      notice.tone === 'success'
                        ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                        : 'bg-yellow-500/10 border border-yellow-500/20 text-yellow-400'
                    )}>
                      {notice.tone === 'success' ? (
                        <CheckCircle className="w-4 h-4 flex-shrink-0" />
                      ) : (
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      )}
                      {notice.text}
                    </div>
                  )}
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center rounded-lg border border-dashed border-augustus-700 py-16">
                  <div className="text-center px-4">
                    <FileText className="w-12 h-12 text-augustus-600 mx-auto mb-4" />
                    <p className="text-augustus-400">Select a file to view or edit</p>
                    {resolveMiss && (
                      <p className="text-xs text-augustus-500 mt-2">
                        Couldn't find the file for "{resolveMiss}".
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function loadNotice(successText: string, name: string | null, available: string[]): Notice {
  if (!name) {
    return { tone: 'warning', text: 'No name property was found, so this file won’t appear as a personality.' }
  }
  if (!available.includes(name)) {
    return { tone: 'warning', text: `"${name}" didn’t load as a personality. Check the file for Python errors.` }
  }
  return { tone: 'success', text: successText }
}
