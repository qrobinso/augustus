import { useState } from 'react'
import type { CastVoices } from '../api/client'
import { CUSTOM_VOICE, voiceChoice } from '../pages/castProviders'

interface VoicePickerProps {
  id: string
  value: string
  onChange: (voiceId: string) => void
  voices: CastVoices | undefined
  loading: boolean
  error?: string
  disabled?: boolean
}

/** Voice dropdown fed by the active provider; free-text only where the provider allows it. */
export default function VoicePicker({ id, value, onChange, voices, loading, error, disabled }: VoicePickerProps) {
  const list = voices?.voices ?? []
  const allowsCustom = voices?.allows_custom ?? false
  const choice = voiceChoice(value, list, allowsCustom)
  const [customOpen, setCustomOpen] = useState(choice.kind === 'custom')
  const showCustom = allowsCustom && (customOpen || choice.kind === 'custom')

  if (error) {
    return <p className="text-sm text-red-400">{error}</p>
  }

  return (
    <div className="space-y-2">
      <select
        id={id}
        className="input w-full"
        disabled={disabled || loading}
        required={!showCustom}
        value={showCustom ? CUSTOM_VOICE : choice.kind === 'listed' ? value : ''}
        onChange={(e) => {
          if (e.target.value === CUSTOM_VOICE) {
            setCustomOpen(true)
            return
          }
          setCustomOpen(false)
          onChange(e.target.value)
        }}
      >
        <option value="" disabled>
          {loading ? 'Loading voices…' : list.length ? 'Choose a voice' : 'No voices available'}
        </option>
        {list.map(v => (
          <option key={v.id} value={v.id}>
            {v.name}{v.description ? ` — ${v.description}` : ''}
          </option>
        ))}
        {allowsCustom && <option value={CUSTOM_VOICE}>Custom voice ID…</option>}
      </select>
      {showCustom && (
        <input
          type="text"
          className="input w-full"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Voice ID"
          required
          disabled={disabled}
        />
      )}
      {choice.kind === 'missing' && (
        <p className="text-xs text-yellow-400">
          “{value}” isn't a {voices?.provider_label} voice. Choose one from the list.
        </p>
      )}
    </div>
  )
}
