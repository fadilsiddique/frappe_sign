import { onScopeDispose, ref, type Ref } from 'vue'

// Below Tailwind's `sm` breakpoint the app uses MobileShell and the mobile page header.
export const MOBILE_QUERY = '(max-width: 639px)'
// From Tailwind's `lg` breakpoint a list can sit beside a preview.
export const WIDE_QUERY = '(min-width: 1024px)'

export function useMatchMedia(queryText: string): Ref<boolean> {
  if (typeof window.matchMedia !== 'function') return ref(false)
  const query = window.matchMedia(queryText)
  const matches = ref(query.matches)
  const update = (event: MediaQueryListEvent) => (matches.value = event.matches)
  query.addEventListener('change', update)
  onScopeDispose(() => query.removeEventListener('change', update))
  return matches
}

export const useIsMobile = () => useMatchMedia(MOBILE_QUERY)
