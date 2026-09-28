import { Volume2 } from 'lucide-react'
import clsx from 'clsx'
import type { AppSettings } from '../../api/client'
import { SecretInput, SettingsCheckbox } from './SettingsControls'

interface TtsSettingsProps {
  settings: AppSettings | undefined
  provider: string
  onProviderChange: (provider: string) => void
  piperUrl: string
  onPiperUrlChange: (value: string) => void
  elevenlabsKey: string
  onElevenlabsKeyChange: (value: string) => void
  elevenlabsModel: string
  onElevenlabsModelChange: (value: string) => void
  geminiKey: string
  onGeminiKeyChange: (value: string) => void
  geminiModel: string
  onGeminiModelChange: (value: string) => void
  enableNonSpeechSounds: boolean
  onEnableNonSpeechSoundsChange: (value: boolean) => void
}

function ProviderOption({
  selected,
  onSelect,
  name,
  ready,
  description,
}: {
  selected: boolean
  onSelect: () => void
  name: string
  ready?: boolean
  description: string
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={clsx(
        'flex-1 p-3 sm:p-4 rounded-lg border-2 transition-all text-left',
        selected
          ? 'border-accent bg-accent/10'
          : 'border-augustus-700 hover:border-augustus-600 active:bg-augustus-800'
      )}
    >
      <div className="font-medium text-white flex items-center gap-2 text-sm sm:text-base">
        {name}
        {ready && (
          <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
            Ready
          </span>
        )}
      </div>
      <div className="text-xs sm:text-sm text-augustus-400">
        {description}
      </div>
    </button>
  )
}

/** Text-to-speech provider choice and the selected provider's configuration. */
export default function TtsSettings({
  settings,
  provider,
  onProviderChange,
  piperUrl,
  onPiperUrlChange,
  elevenlabsKey,
  onElevenlabsKeyChange,
  elevenlabsModel,
  onElevenlabsModelChange,
  geminiKey,
  onGeminiKeyChange,
  geminiModel,
  onGeminiModelChange,
  enableNonSpeechSounds,
  onEnableNonSpeechSoundsChange,
}: TtsSettingsProps) {
  return (
    <div className="card mb-4 sm:mb-6">
      <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
        <Volume2 className="w-5 h-5 text-accent" />
        Text-to-Speech Provider
      </h3>

      <div className="space-y-4">
        <div>
          <label className="label">Provider</label>
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <ProviderOption
              selected={provider === 'piper'}
              onSelect={() => onProviderChange('piper')}
              name="Piper"
              description="Self-hosted, free, good quality"
            />
            <ProviderOption
              selected={provider === 'elevenlabs'}
              onSelect={() => onProviderChange('elevenlabs')}
              name="ElevenLabs"
              ready={settings?.elevenlabs_configured}
              description="Cloud API, premium quality"
            />
            <ProviderOption
              selected={provider === 'gemini'}
              onSelect={() => onProviderChange('gemini')}
              name="Google Gemini"
              ready={settings?.gemini_configured}
              description="Native TTS, expressiveness"
            />
          </div>
        </div>

        {provider === 'piper' && (
          <div>
            <label className="label">
              Piper TTS URL (optional)
            </label>
            <input
              type="text"
              value={piperUrl}
              onChange={(e) => onPiperUrlChange(e.target.value)}
              placeholder="http://localhost:5000"
              className="input"
            />
            <p className="text-xs text-augustus-500 mt-1">
              Leave empty to use local Piper CLI. Set URL to use remote Piper TTS API.
            </p>
          </div>
        )}

        {provider === 'elevenlabs' && (
          <>
            <div>
              <label className="label">
                ElevenLabs API Key
              </label>
              <SecretInput
                value={elevenlabsKey}
                onChange={onElevenlabsKeyChange}
                placeholder={settings?.elevenlabs_api_key || 'Enter ElevenLabs API key'}
              />
            </div>

            <div>
              <label className="label">TTS Model</label>
              <input
                type="text"
                value={elevenlabsModel}
                onChange={(e) => onElevenlabsModelChange(e.target.value)}
                placeholder="eleven_turbo_v2_5"
                className="input"
              />
              <p className="text-xs text-augustus-500 mt-1">
                Default: eleven_turbo_v2_5 (fastest)
              </p>
            </div>
          </>
        )}

        {provider === 'gemini' && (
          <>
            <div>
              <label className="label">
                Gemini API Key
              </label>
              <SecretInput
                value={geminiKey}
                onChange={onGeminiKeyChange}
                placeholder={settings?.gemini_api_key || 'Enter Gemini API key'}
              />
              <p className="text-xs text-augustus-500 mt-1">
                Gemini TTS is currently in preview and requires a Gemini 2.0+ API key.
              </p>
            </div>

            <div>
              <label className="label">TTS Model</label>
              <input
                type="text"
                value={geminiModel}
                onChange={(e) => onGeminiModelChange(e.target.value)}
                placeholder="gemini-2.5-flash-preview-tts"
                className="input"
              />
              <p className="text-xs text-augustus-500 mt-1">
                Default: gemini-2.5-flash-preview-tts
              </p>
            </div>

            <div className="pt-3 border-t border-augustus-700/50">
              <SettingsCheckbox
                checked={enableNonSpeechSounds}
                onChange={onEnableNonSpeechSoundsChange}
                title="Enable Non-speech Sounds"
                description="Add realistic human vocalizations like sighs, laughs, hesitations, and pauses to the podcast script. Uses Gemini's native TTS markup for natural delivery."
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
