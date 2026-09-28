import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { settingsApi } from '../../api/client'
import { apiErrorMessage, isServerUrl } from './settingsLogic'

interface VoiceboxSettingsProps {
  url: string
  /** The saved URL, to tell a cleared field from one never set. */
  savedUrl: string | null | undefined
  onUrlChange: (value: string) => void
  model: string
  onModelChange: (value: string) => void
}

type TestResult = Awaited<ReturnType<typeof settingsApi.validateVoicebox>>

/** Connect a self-hosted Voicebox server and choose the model its cloned voices use. */
export default function VoiceboxSettings({ url, savedUrl, onUrlChange, model, onModelChange }: VoiceboxSettingsProps) {
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<TestResult | null>(null)
  const validUrl = isServerUrl(url)
  // Clearing the saved URL while Voicebox is selected is held back until another provider is chosen.
  const clearedWhileSelected = !url.trim() && !!savedUrl

  const { data: models, isLoading: modelsLoading, error: modelsError } = useQuery({
    queryKey: ['voicebox-models', url.trim()],
    queryFn: () => settingsApi.getVoiceboxModels(url.trim()),
    enabled: validUrl,
    staleTime: 60_000,
    retry: false,
  })

  const testConnection = async () => {
    setTesting(true)
    try {
      setResult(await settingsApi.validateVoicebox(url.trim()))
    } catch (error) {
      setResult({ valid: false, message: apiErrorMessage(error), version: null, voice_count: 0, warning: null })
    } finally {
      setTesting(false)
    }
  }

  return (
    <>
      <div>
        <label className="label" htmlFor="voicebox-url">Voicebox server URL</label>
        <div className="flex gap-2">
          <input
            id="voicebox-url"
            type="url"
            value={url}
            onChange={(e) => { onUrlChange(e.target.value); setResult(null) }}
            placeholder="http://localhost:17493"
            className="input flex-1"
          />
          <button type="button" className="btn btn-secondary" onClick={testConnection} disabled={!validUrl || testing}>
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Test connection'}
          </button>
        </div>
        <p className={`text-xs mt-1 ${clearedWhileSelected ? 'text-yellow-400' : 'text-augustus-500'}`}>
          Where your Voicebox app is running. Clear it to disconnect (choose another provider first).
        </p>
        {!url.trim() && !clearedWhileSelected && (
          <p className="text-xs text-yellow-400 mt-1">Add your Voicebox server URL to use Voicebox.</p>
        )}
        {url.trim() && !validUrl && (
          <p className="text-xs text-red-400 mt-1">Start the URL with http:// or https://</p>
        )}
        {result && (
          <p className={`mt-2 flex items-center gap-1.5 text-sm ${result.valid ? 'text-green-400' : 'text-red-400'}`}>
            {result.valid ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {result.message}
          </p>
        )}
        {result?.warning && <p className="mt-1 text-xs text-yellow-400">{result.warning}</p>}
      </div>

      <div>
        <label className="label" htmlFor="voicebox-model">Model</label>
        <select
          id="voicebox-model"
          className="input w-full"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          disabled={!validUrl || modelsLoading || !!modelsError}
        >
          <option value="">{modelsLoading ? 'Loading models…' : 'First available model'}</option>
          {(models ?? []).map(m => (
            <option key={m.name} value={m.name}>{m.display_name}</option>
          ))}
        </select>
        <p className="text-xs text-augustus-500 mt-1">
          {modelsError
            ? `Couldn't load models: ${apiErrorMessage(modelsError)}`
            : 'Used for your cloned voices. Preset voices always use their own engine.'}
        </p>
      </div>
    </>
  )
}
