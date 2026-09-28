import { describe, expect, it } from 'vitest'
import {
  applyPersonalityChange,
  findPersonalityFile,
  guessPersonalityFile,
  parsePersonalityName,
  validatePersonalityFilename,
} from './personalityFiles'

const FILE = `"""Scholar personality."""

from app.services.llm.personalities.base import Personality


class Scholar(Personality):
    @property
    def name(self) -> str:
        return "The Scholar/Researcher"

    @property
    def voice(self) -> str:
        return "Measured"
`

describe('parsePersonalityName', () => {
  it('reads the name property, not other properties', () => {
    expect(parsePersonalityName(FILE)).toBe('The Scholar/Researcher')
  })

  it('handles a docstring and single quotes', () => {
    expect(parsePersonalityName(`def name(self) -> str:\n    """Doc."""\n    return 'Envy'`)).toBe('Envy')
  })

  it('returns null when there is no name property', () => {
    expect(parsePersonalityName('class X: pass')).toBeNull()
  })
})

describe('guessPersonalityFile', () => {
  const files = ['scholar.py', 'casual.py', 'provocateur.py', 'businessman.py']

  it('maps display names to files by convention', () => {
    expect(guessPersonalityFile('The Scholar/Researcher', files)).toBe('scholar.py')
    expect(guessPersonalityFile('Casual', files)).toBe('casual.py')
    expect(guessPersonalityFile('The Provocateur/Truth-Teller', files)).toBe('provocateur.py')
  })

  it('returns null when nothing matches', () => {
    expect(guessPersonalityFile('Envy', files)).toBeNull()
  })
})

describe('findPersonalityFile', () => {
  const contents: Record<string, string> = {
    'scholar.py': FILE,
    'businessman.py': 'def name(self) -> str:\n    return "Envy"',
    'casual.py': 'def name(self) -> str:\n    return "Casual"',
  }
  const read = async (f: string) => ({ content: contents[f] })
  const files = Object.keys(contents)

  it('verifies the conventional guess', async () => {
    expect(await findPersonalityFile('The Scholar/Researcher', files, read)).toBe('scholar.py')
  })

  it('scans file contents when the name does not follow convention', async () => {
    expect(await findPersonalityFile('Envy', files, read)).toBe('businessman.py')
  })

  it('falls back to the unverified guess for aliases', async () => {
    expect(await findPersonalityFile('The Businessman/Everyman', files, read)).toBe('businessman.py')
  })

  it('returns null when nothing matches', async () => {
    expect(await findPersonalityFile('Nobody', files, read)).toBeNull()
  })
})

describe('validatePersonalityFilename', () => {
  it('normalizes to a .py filename', () => {
    expect(validatePersonalityFilename(' night_owl ', [])).toEqual({ filename: 'night_owl.py', error: null })
    expect(validatePersonalityFilename('night_owl.py', [])).toEqual({ filename: 'night_owl.py', error: null })
  })

  it('rejects empty, invalid, reserved, and duplicate names', () => {
    expect(validatePersonalityFilename('  ', []).error).toBeTruthy()
    expect(validatePersonalityFilename('night-owl', []).error).toBeTruthy()
    expect(validatePersonalityFilename('1host', []).error).toBeTruthy()
    expect(validatePersonalityFilename('base', []).error).toBeTruthy()
    expect(validatePersonalityFilename('Casual', ['casual.py']).error).toBeTruthy()
  })
})

describe('applyPersonalityChange', () => {
  const members = [
    { name: 'A', personality: 'Casual' },
    { name: 'B', personality: 'Casual' },
  ]

  it('selects a created personality for the target member only', () => {
    const next = applyPersonalityChange(members, {
      type: 'created', filename: 'owl.py', previousName: null, name: 'Owl', available: ['Casual', 'Owl'],
    }, 1)
    expect(next.map((m) => m.personality)).toEqual(['Casual', 'Owl'])
  })

  it('does not select a created personality that failed to load', () => {
    const next = applyPersonalityChange(members, {
      type: 'created', filename: 'owl.py', previousName: null, name: 'Owl', available: ['Casual'],
    }, 1)
    expect(next).toEqual(members)
  })

  it('follows a renamed personality', () => {
    const next = applyPersonalityChange(members, {
      type: 'saved', filename: 'casual.py', previousName: 'Casual', name: 'Laid Back', available: ['Laid Back', 'Upbeat'],
    }, 0)
    expect(next.map((m) => m.personality)).toEqual(['Laid Back', 'Laid Back'])
  })

  it('falls back to the first personality when one is deleted', () => {
    const next = applyPersonalityChange(members, {
      type: 'deleted', filename: 'casual.py', previousName: 'Casual', name: null, available: ['Upbeat'],
    }, null)
    expect(next.map((m) => m.personality)).toEqual(['Upbeat', 'Upbeat'])
  })
})
