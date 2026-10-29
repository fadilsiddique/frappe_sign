// Times and dates for the staff app. The server sends seconds ago and plain YYYY-MM-DD dates, so
// the browser's time zone never shifts them.
import { __ } from '@/shared/translate'

const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

export function timeAgo(seconds: number): string {
  if (seconds < MINUTE) return __('just now')
  if (seconds < HOUR) {
    const minutes = Math.floor(seconds / MINUTE)
    return minutes === 1 ? __('1 minute ago') : __('{0} minutes ago', [minutes])
  }
  if (seconds < DAY) {
    const hours = Math.floor(seconds / HOUR)
    return hours === 1 ? __('1 hour ago') : __('{0} hours ago', [hours])
  }
  const days = Math.floor(seconds / DAY)
  return days === 1 ? __('yesterday') : __('{0} days ago', [days])
}

// "5 Nov", with the year when it is not this year: "5 Nov 2027".
export function shortDate(
  isoDate: string,
  lang = document.documentElement.lang || 'en',
  now = new Date(),
): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', timeZone: 'UTC' }
  if (date.getUTCFullYear() !== now.getFullYear()) options.year = 'numeric'
  return new Intl.DateTimeFormat(lang, options).format(date)
}

export function monthName(lang = document.documentElement.lang || 'en', now = new Date()): string {
  return new Intl.DateTimeFormat(lang, { month: 'long' }).format(now)
}
