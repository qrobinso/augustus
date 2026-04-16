import { useCallback } from 'react'
import { useNavigate, NavigateOptions } from 'react-router-dom'
import { useStore } from '../store/useStore'

/**
 * Convert a profile name to a URL-safe slug.
 * e.g. "Quinn Robinson" → "quinn-robinson"
 */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/**
 * Get the slug for the current profile from the store.
 */
export function useProfileSlug(): string {
  const currentProfile = useStore((s) => s.currentProfile)
  return currentProfile ? slugify(currentProfile.name) : ''
}

/**
 * Prefix a path with the current profile slug.
 * Paths starting with '/' get the profile slug prepended.
 * Special routes (/profiles, /onboarding) are returned as-is.
 */
export function useProfilePath() {
  const slug = useProfileSlug()

  return useCallback(
    (path: string): string => {
      // Don't prefix special routes
      if (
        path === '/' ||
        path.startsWith('/profiles') ||
        path.startsWith('/onboarding')
      ) {
        return path
      }
      return `/${slug}${path.startsWith('/') ? path : `/${path}`}`
    },
    [slug]
  )
}

/**
 * A wrapper around useNavigate that auto-prefixes profile slug.
 * Use this as a drop-in replacement for useNavigate().
 */
export function useProfileNavigate() {
  const navigate = useNavigate()
  const profilePath = useProfilePath()

  return useCallback(
    (to: string | number, options?: NavigateOptions) => {
      if (typeof to === 'number') {
        navigate(to)
      } else {
        navigate(profilePath(to), options)
      }
    },
    [navigate, profilePath]
  )
}
