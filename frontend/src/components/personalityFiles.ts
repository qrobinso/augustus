import axios from 'axios'

/** A change made in the personality editor, reported once the personality list is fresh. */
export interface PersonalityChange {
  type: 'created' | 'saved' | 'deleted'
  filename: string
  /** Personality name declared by the file before the change (null for creates or unparseable files). */
  previousName: string | null
  /** Personality name declared by the file after the change (null for deletes or unparseable files). */
  name: string | null
  /** The refreshed list of selectable personality names. */
  available: string[]
}

const RESERVED_STEMS = new Set(['__init__', 'base'])

/**
 * Extract the display name a personality file declares via its
 * `name` property (`def name(self) -> str: return "..."`).
 */
export function parsePersonalityName(content: string): string | null {
  const match = content.match(
    /def\s+name\s*\(\s*self\s*\)[^:]*:\s*(?:(?:"""[\s\S]*?"""|'''[\s\S]*?''')\s*)?return\s+(["'])((?:\\.|(?!\1).)*)\1/,
  )
  return match ? match[2].replace(/\\(["'\\])/g, '$1') : null
}

function simplify(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, '')
}

/**
 * Best-guess file for a personality display name, from naming convention
 * ("The Scholar/Researcher" -> scholar.py). Callers should confirm the
 * guess against the file's declared name.
 */
export function guessPersonalityFile(personality: string, filenames: string[]): string | null {
  const primary = personality.replace(/^the\s+/i, '').split('/')[0]
  const key = simplify(primary)
  if (!key) return null
  return filenames.find((f) => simplify(f.replace(/\.py$/, '')) === key) ?? null
}

/**
 * Find the file that declares a personality. The naming-convention guess
 * is checked first, then every other file; if no file declares the name
 * (e.g. a legacy registry alias), the unverified guess is used.
 */
export async function findPersonalityFile(
  personality: string,
  filenames: string[],
  readFile: (filename: string) => Promise<{ content: string }>,
): Promise<string | null> {
  const declares = async (filename: string) => {
    try {
      return parsePersonalityName((await readFile(filename)).content) === personality
    } catch {
      return false
    }
  }
  const guess = guessPersonalityFile(personality, filenames)
  if (guess && (await declares(guess))) return guess
  const rest = filenames.filter((f) => f !== guess)
  const matches = await Promise.all(rest.map(declares))
  const found = rest.find((_, i) => matches[i])
  return found ?? guess
}

/** Normalize a user-entered filename to `stem.py`, or return an error message. */
export function validatePersonalityFilename(
  input: string,
  existing: string[],
): { filename: string; error: null } | { filename: null; error: string } {
  const trimmed = input.trim()
  if (!trimmed) return { filename: null, error: 'Enter a filename' }
  const stem = trimmed.replace(/\.py$/, '')
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(stem)) {
    return {
      filename: null,
      error: 'Use letters, numbers, and underscores only, starting with a letter',
    }
  }
  if (RESERVED_STEMS.has(stem)) return { filename: null, error: `"${stem}.py" is reserved` }
  const filename = `${stem}.py`
  if (existing.some((f) => f.toLowerCase() === filename.toLowerCase())) {
    return { filename: null, error: `"${filename}" already exists` }
  }
  return { filename, error: null }
}

export function personalityErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return error instanceof Error ? error.message : fallback
}

/**
 * Apply an editor change to cast members' personality selections:
 * a created personality is selected for the target member, a renamed
 * personality follows its members, and any member whose personality
 * no longer exists falls back to the first available one.
 */
export function applyPersonalityChange<M extends { personality: string }>(
  members: M[],
  change: PersonalityChange,
  targetIndex: number | null,
): M[] {
  const { available } = change
  return members.map((member, index) => {
    let personality = member.personality
    if (
      change.type === 'created' &&
      index === targetIndex &&
      change.name &&
      available.includes(change.name)
    ) {
      personality = change.name
    } else if (
      change.type === 'saved' &&
      change.previousName &&
      change.name &&
      change.previousName !== change.name &&
      personality === change.previousName &&
      available.includes(change.name)
    ) {
      personality = change.name
    }
    if (available.length > 0 && !available.includes(personality)) {
      personality = available[0]
    }
    return personality === member.personality ? member : { ...member, personality }
  })
}
