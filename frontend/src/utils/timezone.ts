/**
 * Timezone utilities for date/time display.
 * Dates from the backend are stored in UTC and should be displayed in the user's configured timezone.
 */

import { settingsApi } from '../api/client'

// Cache the timezone setting
let cachedTimezone: string | null = null

/**
 * Get the user's configured timezone from settings.
 * Falls back to browser's timezone if not set.
 */
export async function getUserTimezone(): Promise<string> {
  if (cachedTimezone) return cachedTimezone
  
  try {
    const settings = await settingsApi.get()
    cachedTimezone = settings.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone
    return cachedTimezone
  } catch {
    return Intl.DateTimeFormat().resolvedOptions().timeZone
  }
}

/**
 * Set the cached timezone (call this when settings are loaded).
 */
export function setTimezoneCache(timezone: string): void {
  cachedTimezone = timezone
}

/**
 * Clear the timezone cache (call this when settings are updated).
 */
export function clearTimezoneCache(): void {
  cachedTimezone = null
}

/**
 * Format a date string (ISO format from backend) to local timezone.
 * 
 * @param dateStr - ISO date string from backend (UTC)
 * @param timezone - IANA timezone name (e.g., "America/New_York")
 * @param options - Intl.DateTimeFormat options
 * @returns Formatted date string in local timezone
 */
export function formatDateInTimezone(
  dateStr: string,
  timezone: string,
  options?: Intl.DateTimeFormatOptions
): string {
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    
    const defaultOptions: Intl.DateTimeFormatOptions = {
      timeZone: timezone,
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      ...options,
    }
    
    return new Intl.DateTimeFormat('en-US', defaultOptions).format(date)
  } catch {
    // Fallback to basic formatting if timezone is invalid
    return new Date(dateStr).toLocaleString()
  }
}

/**
 * Format a date for display with weekday.
 */
export function formatFullDate(dateStr: string, timezone: string): string {
  return formatDateInTimezone(dateStr, timezone, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format a date for compact display.
 */
export function formatCompactDate(dateStr: string, timezone: string): string {
  return formatDateInTimezone(dateStr, timezone, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format a relative time string (e.g., "2 hours ago").
 */
export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)
  
  if (diffSecs < 60) return 'Just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`
  
  // Fall back to date display for older dates
  return formatCompactDate(dateStr, Intl.DateTimeFormat().resolvedOptions().timeZone)
}

/**
 * Get the current time in a specific timezone.
 */
export function getCurrentTimeInTimezone(timezone: string): Date {
  const now = new Date()
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  
  const parts = formatter.formatToParts(now)
  const values: Record<string, string> = {}
  parts.forEach(part => {
    values[part.type] = part.value
  })
  
  return new Date(
    `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}:${values.second}`
  )
}



