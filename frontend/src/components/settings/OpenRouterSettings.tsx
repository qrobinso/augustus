import { useMemo, useRef, useState } from 'react'
import { ChevronDown, Cpu, ExternalLink, Info, Loader2, Search } from 'lucide-react'
import clsx from 'clsx'
import type { AppSettings, ModelOption } from '../../api/client'
import { SecretInput } from './SettingsControls'
import { filterModels, formatContextLength, groupModelsByProvider } from './settingsLogic'

type DropdownPosition = { top: number; left: number; width: number }

interface OpenRouterSettingsProps {
  settings: AppSettings | undefined
  models: ModelOption[] | undefined
  modelsLoading: boolean
  apiKey: string
  onApiKeyChange: (value: string) => void
  model: string
  onModelChange: (modelId: string) => void
  writerModel: string
  onWriterModelChange: (modelId: string) => void
}

function measureDropdown(button: HTMLButtonElement | null): DropdownPosition | null {
  if (!button) return null
  const rect = button.getBoundingClientRect()
  return {
    top: rect.bottom + 8,
    left: rect.left,
    width: Math.min(rect.width, window.innerWidth - 32),
  }
}

/** Model rows grouped under provider headers, shared by both model pickers. */
function ModelList({
  loading,
  models,
  selectedId,
  onSelect,
}: {
  loading: boolean
  models: ModelOption[]
  selectedId: string
  onSelect: (modelId: string) => void
}) {
  const grouped = groupModelsByProvider(models)

  if (loading) {
    return (
      <div className="p-4 text-center">
        <Loader2 className="w-5 h-5 animate-spin text-accent mx-auto" />
        <p className="text-sm text-augustus-500 mt-2">Loading models...</p>
      </div>
    )
  }

  if (Object.keys(grouped).length === 0) {
    return (
      <div className="p-4 text-center text-augustus-500 text-sm">
        No models found
      </div>
    )
  }

  return (
    <>
      {Object.entries(grouped).map(([provider, providerModels]) => (
        <div key={provider}>
          <div className="px-3 py-2 bg-augustus-800/50 text-xs font-semibold text-augustus-400 uppercase tracking-wide sticky top-0">
            {provider}
          </div>
          {providerModels.map((model) => (
            <button
              key={model.id}
              type="button"
              onClick={() => onSelect(model.id)}
              className={clsx(
                'w-full px-3 py-3 sm:py-2 text-left hover:bg-augustus-800 active:bg-augustus-700 transition-colors flex items-center justify-between',
                model.id === selectedId && 'bg-accent/10 border-l-2 border-accent'
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
              </div>
            </button>
          ))}
        </div>
      ))}
    </>
  )
}

function ModelSearchInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="p-2 sm:p-2 border-b border-augustus-700">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-augustus-500" />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Search models..."
          className="w-full pl-9 pr-4 py-2.5 sm:py-2 bg-augustus-800 border border-augustus-700 rounded-lg text-white text-sm placeholder-augustus-500 focus:outline-none focus:border-accent"
          autoFocus
        />
      </div>
    </div>
  )
}

const sheetClassName = clsx(
  'fixed z-[9999] bg-augustus-900 border border-augustus-700 shadow-2xl overflow-hidden',
  // Mobile: bottom sheet style
  'inset-x-0 bottom-0 rounded-t-2xl max-h-[70vh]',
  // Desktop: dropdown style
  'sm:inset-auto sm:rounded-lg sm:max-h-96'
)

const sheetStyle = (position: DropdownPosition) => ({
  ...(window.innerWidth >= 640 && {
    top: position.top,
    left: position.left,
    width: position.width,
  }),
})

const modelCountLabel = (count: number) => `${count} model${count !== 1 ? 's' : ''} available`

/**
 * OpenRouter API key plus standard and writer model pickers. Form values are owned by
 * the Settings page (which auto-saves them); only picker UI state lives here.
 */
export default function OpenRouterSettings({
  settings,
  models,
  modelsLoading,
  apiKey,
  onApiKeyChange,
  model,
  onModelChange,
  writerModel,
  onWriterModelChange,
}: OpenRouterSettingsProps) {
  const [modelSearch, setModelSearch] = useState('')
  const [showModelDropdown, setShowModelDropdown] = useState(false)
  const modelButtonRef = useRef<HTMLButtonElement>(null)
  const [dropdownPosition, setDropdownPosition] = useState<DropdownPosition>({ top: 0, left: 0, width: 0 })
  const [writerModelSearch, setWriterModelSearch] = useState('')
  const [showWriterModelDropdown, setShowWriterModelDropdown] = useState(false)
  const writerModelButtonRef = useRef<HTMLButtonElement>(null)
  const [writerDropdownPosition, setWriterDropdownPosition] = useState<DropdownPosition>({ top: 0, left: 0, width: 0 })

  const filteredModels = useMemo(() => filterModels(models ?? [], modelSearch), [models, modelSearch])
  const writerFilteredModels = useMemo(
    () => filterModels(filteredModels, writerModelSearch),
    [filteredModels, writerModelSearch],
  )

  const selectedModel = useMemo(() => models?.find(m => m.id === model), [models, model])
  const selectedWriterModel = useMemo(() => models?.find(m => m.id === writerModel), [models, writerModel])

  const handleOpenModelDropdown = () => {
    const position = measureDropdown(modelButtonRef.current)
    if (position) setDropdownPosition(position)
    setShowModelDropdown(!showModelDropdown)
  }

  const handleOpenWriterModelDropdown = () => {
    const position = measureDropdown(writerModelButtonRef.current)
    if (position) setWriterDropdownPosition(position)
    setShowWriterModelDropdown(!showWriterModelDropdown)
  }

  const closeModelDropdown = () => {
    setShowModelDropdown(false)
    setModelSearch('')
  }

  const closeWriterModelDropdown = () => {
    setShowWriterModelDropdown(false)
    setWriterModelSearch('')
  }

  return (
    <>
      <div className="card mb-4 sm:mb-6 overflow-visible">
        <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2 flex-wrap">
          <Cpu className="w-5 h-5 text-accent flex-shrink-0" />
          <span>LLM Provider (OpenRouter)</span>
          {settings?.openrouter_configured ? (
            <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">
              Configured
            </span>
          ) : (
            <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
              Not configured
            </span>
          )}
        </h3>

        <p className="text-xs sm:text-sm text-augustus-400 mb-3 sm:mb-4">
          OpenRouter provides access to multiple AI models.{' '}
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
            <SecretInput
              value={apiKey}
              onChange={onApiKeyChange}
              placeholder={settings?.openrouter_api_key || 'sk-or-...'}
            />
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
                  <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                    <span className="text-white text-sm sm:text-base truncate">{selectedModel.name}</span>
                    <span className="text-augustus-500 text-xs sm:text-sm hidden sm:inline">({selectedModel.provider})</span>
                  </div>
                ) : (
                  <span className="text-augustus-500 text-sm sm:text-base">Select a model...</span>
                )}
              </div>
              <ChevronDown className={clsx(
                'w-5 h-5 text-augustus-500 transition-transform flex-shrink-0',
                showModelDropdown && 'rotate-180'
              )} />
            </button>
          </div>

          <div>
            <label className="label flex items-center gap-2">
              Writer Model
              <div className="group relative">
                <Info className="w-4 h-4 text-augustus-500 hover:text-augustus-300 cursor-help" />
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-augustus-800 border border-augustus-700 rounded-lg shadow-lg text-xs text-augustus-300 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10 pointer-events-none">
                  <div className="font-semibold text-white mb-1">Writer Model</div>
                  <div className="mb-2">Used specifically for briefing writing, which requires more detailed thinking and analysis. If not set, the standard model above will be used.</div>
                  <div className="font-semibold text-white mb-1">Standard Model</div>
                  <div>Used for all other operations (story analysis, facts gathering, etc.).</div>
                </div>
              </div>
            </label>
            <p className="text-xs sm:text-sm text-augustus-500 mb-2">
              Optional. A separate model for briefing writing. If not set, uses the standard model above.
            </p>

            {/* Selected writer model display / dropdown trigger */}
            <button
              ref={writerModelButtonRef}
              type="button"
              onClick={handleOpenWriterModelDropdown}
              className="input w-full text-left flex items-center justify-between"
            >
              <div className="flex-1 min-w-0">
                {selectedWriterModel ? (
                  <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                    <span className="text-white text-sm sm:text-base truncate">{selectedWriterModel.name}</span>
                    <span className="text-augustus-500 text-xs sm:text-sm hidden sm:inline">({selectedWriterModel.provider})</span>
                  </div>
                ) : (
                  <span className="text-augustus-500 text-sm sm:text-base">Use standard model (leave empty)</span>
                )}
              </div>
              <ChevronDown className={clsx(
                'w-5 h-5 text-augustus-500 transition-transform flex-shrink-0',
                showWriterModelDropdown && 'rotate-180'
              )} />
            </button>
          </div>
        </div>
      </div>

      {/* Writer Model Dropdown - on mobile, a bottom sheet */}
      {showWriterModelDropdown && (
        <div className="fixed inset-0 z-[9998] sm:z-[9998]" onClick={closeWriterModelDropdown}>
          <div
            className={sheetClassName}
            style={sheetStyle(writerDropdownPosition)}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Mobile handle */}
            <div className="sm:hidden w-10 h-1 bg-augustus-600 rounded-full mx-auto mt-3 mb-2" />

            <ModelSearchInput value={writerModelSearch} onChange={setWriterModelSearch} />

            {/* Clear option */}
            <button
              type="button"
              onClick={() => {
                onWriterModelChange('')
                closeWriterModelDropdown()
              }}
              className="w-full px-3 py-2 text-left hover:bg-augustus-800 active:bg-augustus-700 transition-colors text-augustus-400 text-sm border-b border-augustus-700"
            >
              Use standard model (leave empty)
            </button>

            <div className="overflow-y-auto max-h-[50vh] sm:max-h-72">
              <ModelList
                loading={modelsLoading}
                models={writerFilteredModels}
                selectedId={writerModel}
                onSelect={(modelId) => {
                  onWriterModelChange(modelId)
                  closeWriterModelDropdown()
                }}
              />
            </div>

            <div className="p-2 border-t border-augustus-700 text-xs text-augustus-500 text-center pb-safe">
              {modelCountLabel(writerFilteredModels.length)}
            </div>
          </div>
        </div>
      )}

      {/* Model Dropdown - on mobile, a bottom sheet */}
      {showModelDropdown && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-[9998]" onClick={closeModelDropdown} />

          <div className={sheetClassName} style={sheetStyle(dropdownPosition)}>
            {/* Mobile handle */}
            <div className="sm:hidden w-10 h-1 bg-augustus-600 rounded-full mx-auto mt-3 mb-2" />

            <ModelSearchInput value={modelSearch} onChange={setModelSearch} />

            <div className="overflow-y-auto max-h-[50vh] sm:max-h-72">
              <ModelList
                loading={modelsLoading}
                models={filteredModels}
                selectedId={model}
                onSelect={(modelId) => {
                  onModelChange(modelId)
                  closeModelDropdown()
                }}
              />
            </div>

            <div className="p-2 border-t border-augustus-700 text-xs text-augustus-500 text-center pb-safe">
              {modelCountLabel(filteredModels.length)}
            </div>
          </div>
        </>
      )}
    </>
  )
}
