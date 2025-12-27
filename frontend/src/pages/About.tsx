import { useEffect } from 'react'
import { 
  Info,
  Code,
  User,
  Github,
  ExternalLink,
  Sparkles
} from 'lucide-react'

export default function About() {
  // Scroll to top when component mounts
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="page-container max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-display font-semibold text-white mb-1 sm:mb-2 flex items-center gap-2">
          <Info className="w-6 h-6 sm:w-7 sm:h-7 text-accent" />
          About
        </h1>
        <p className="text-sm sm:text-base text-augustus-400">
          Information about Augustus and its creator
        </p>
      </div>

      {/* App Information */}
      <div className="card mb-4 sm:mb-6">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-accent" />
          About Augustus
        </h2>
        <div className="space-y-3 sm:space-y-4 text-sm sm:text-base text-augustus-300">
          <p>
            Augustus is an AI-powered audio intelligence platform that transforms your news feeds into personalized, 
            conversational podcast briefings. Stay informed with daily briefings tailored to your interests, delivered 
            in a natural, engaging format.
          </p>
          <p>
            The platform uses advanced language models to analyze news articles, extract key insights, and generate 
            high-quality audio content with multiple voice personalities. You can customize topics, schedules, and 
            even create your own podcast "casts" with unique personalities.
          </p>
          <div className="pt-3 sm:pt-4 border-t border-augustus-800">
            <h3 className="text-sm font-semibold text-white mb-2">Key Features</h3>
            <ul className="space-y-2 list-disc list-inside text-augustus-400">
              <li>AI-generated daily briefings from your selected topics</li>
              <li>Customizable podcast personalities and voices</li>
              <li>Scheduled briefings with email and webhook notifications</li>
              <li>Custom news site integration</li>
              <li>Self-hosted and privacy-focused</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Creator Information */}
      <div className="card mb-4 sm:mb-6">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <User className="w-5 h-5 text-accent" />
          Creator
        </h2>
        <div className="space-y-3 sm:space-y-4 text-sm sm:text-base text-augustus-300">
          <p>
            Augustus was created as an open-source project to provide a self-hosted alternative to commercial 
            news briefing services. The platform prioritizes privacy, customization, and user control.
          </p>
          <div className="pt-3 sm:pt-4 border-t border-augustus-800">
            <h3 className="text-sm font-semibold text-white mb-3">Open Source</h3>
            <p className="mb-3 text-augustus-400">
              Augustus is open source and available on GitHub. Contributions, issues, and feature requests are welcome.
            </p>
            <a
              href="https://github.com/qrobinso/augustus"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 bg-augustus-800 hover:bg-augustus-700 text-white rounded-lg transition-colors border border-augustus-700 hover:border-augustus-600 active:scale-95"
            >
              <Github className="w-4 h-4" />
              <span>View on GitHub</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>

      {/* Technology Stack */}
      <div className="card">
        <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 flex items-center gap-2">
          <Code className="w-5 h-5 text-accent" />
          Technology
        </h2>
        <div className="space-y-3 text-sm sm:text-base text-augustus-300">
          <p className="text-augustus-400">
            Built with modern web technologies and AI services:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div className="p-3 bg-augustus-900/50 rounded-lg border border-augustus-800">
              <h4 className="text-xs font-semibold text-augustus-400 uppercase tracking-wide mb-2">Frontend</h4>
              <ul className="space-y-1 text-xs text-augustus-300">
                <li>• React + TypeScript</li>
                <li>• Vite</li>
                <li>• Tailwind CSS</li>
                <li>• React Query</li>
              </ul>
            </div>
            <div className="p-3 bg-augustus-900/50 rounded-lg border border-augustus-800">
              <h4 className="text-xs font-semibold text-augustus-400 uppercase tracking-wide mb-2">Backend</h4>
              <ul className="space-y-1 text-xs text-augustus-300">
                <li>• FastAPI (Python)</li>
                <li>• SQLAlchemy</li>
                <li>• OpenRouter API</li>
                <li>• TTS Services</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}










