import { SlidersHorizontal } from 'lucide-react'
import clsx from 'clsx'
import { getComplexityLabel, getDurationLabel } from './settingsLogic'

function LevelMarkers({ levels, value }: { levels: number; value: number }) {
  return (
    <div className="flex justify-between mt-1 px-1">
      {Array.from({ length: levels }, (_, i) => i + 1).map((level) => (
        <div
          key={level}
          className={clsx(
            'w-2 h-2 rounded-full transition-colors',
            level <= value ? 'bg-accent' : 'bg-augustus-600'
          )}
        />
      ))}
    </div>
  )
}

/** Briefing length and conversation complexity sliders. */
export default function ContentSettings({
  durationSlider,
  onDurationSliderChange,
  complexity,
  onComplexityChange,
}: {
  durationSlider: number
  onDurationSliderChange: (value: number) => void
  complexity: number
  onComplexityChange: (value: number) => void
}) {
  return (
    <div className="card mb-4 sm:mb-6">
      <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
        <SlidersHorizontal className="w-5 h-5 text-accent" />
        Length & complexity
      </h3>

      <div className="space-y-4">
        {/* Duration Configuration */}
        <div>
          <h4 className="text-sm font-medium text-white mb-2 sm:mb-3">Content Duration</h4>
          <p className="text-xs text-augustus-400 mb-3 sm:mb-4">
            Target duration for audio content
          </p>

          <div className="flex justify-between items-center mb-2">
            <label className="label text-xs sm:text-sm mb-0">Daily Briefing</label>
            <span className="text-xs sm:text-sm font-medium text-white">
              {getDurationLabel(durationSlider)}
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={3}
            step={1}
            value={durationSlider}
            onChange={(e) => onDurationSliderChange(parseInt(e.target.value))}
            aria-label="Daily briefing duration"
            className="w-full h-2 bg-augustus-700 rounded-lg appearance-none cursor-pointer accent-accent"
          />
          <div className="flex justify-between mt-1 px-1">
            <span className="text-xs text-augustus-500">Short</span>
            <span className="text-xs text-augustus-500">Medium</span>
            <span className="text-xs text-augustus-500">Long</span>
          </div>
          <LevelMarkers levels={3} value={durationSlider} />
        </div>

        {/* Conversation Complexity */}
        <div className="pt-4 border-t border-augustus-700">
          <h4 className="text-sm font-medium text-white mb-2 sm:mb-3">Language & Complexity</h4>

          <div className="flex justify-between items-center mb-2">
            <span className="text-xs text-augustus-400">Casual</span>
            <span className="text-xs sm:text-sm font-medium text-white">
              {getComplexityLabel(complexity)}
            </span>
            <span className="text-xs text-augustus-400">Expert</span>
          </div>

          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={complexity}
            onChange={(e) => onComplexityChange(parseInt(e.target.value))}
            aria-label="Language and complexity"
            className="w-full h-2 bg-augustus-700 rounded-lg appearance-none cursor-pointer accent-accent"
          />

          <LevelMarkers levels={5} value={complexity} />
        </div>
      </div>
    </div>
  )
}
