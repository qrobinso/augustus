import { AlertCircle, Cpu, Loader2 } from 'lucide-react'
import clsx from 'clsx'

export type LlmProvider = 'openrouter' | 'codex'

const PROVIDER_OPTIONS: { id: LlmProvider; name: string; description: string }[] = [
  { id: 'openrouter', name: 'OpenRouter', description: 'Use an API key and choose from OpenRouter models.' },
  { id: 'codex', name: 'Codex subscription', description: 'Use your connected ChatGPT subscription allowance.' },
]

/**
 * Radio switch between text generation providers. Presentational only: the Settings page
 * owns the provider state and its immediate (non-debounced) save.
 */
export default function TextGenerationProvider({
  provider,
  onChange,
  saving,
  error,
}: {
  provider: LlmProvider
  onChange: (provider: LlmProvider) => void
  saving: boolean
  error: string | null
}) {
  return (
    <div className="card mb-4 sm:mb-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-base font-semibold text-white sm:text-lg">
            <Cpu className="h-5 w-5 flex-shrink-0 text-accent" />
            Text generation
          </h3>
          <p className="mt-1 text-xs text-augustus-400 sm:text-sm">
            Choose how Augustus generates analysis, research, and briefing scripts.
          </p>
        </div>
        {saving && (
          <span className="inline-flex items-center gap-1.5 text-xs text-augustus-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Saving provider…
          </span>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Text generation provider">
        {PROVIDER_OPTIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={provider === option.id}
            onClick={() => onChange(option.id)}
            disabled={saving}
            className={clsx(
              'min-h-[68px] rounded-lg border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60',
              provider === option.id
                ? 'border-accent bg-accent/10'
                : 'border-augustus-700 bg-augustus-900 hover:border-augustus-600',
            )}
          >
            <span className="block text-sm font-medium text-white">{option.name}</span>
            <span className="mt-1 block text-xs text-augustus-400">{option.description}</span>
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
