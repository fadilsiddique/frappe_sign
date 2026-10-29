// The Sent page's data: the list (with "load more"), the tab counts and the Filter menu's choices.
// Each change of filters starts again; a slow earlier answer never overwrites a newer one.
import { reactive, watch, type Ref } from 'vue'
import { staff } from '../api'
import type { FilterOptions, RequestCounts, RequestFilters, RequestRow, Tab } from './types'

export interface RequestList {
  data: RequestRow[] | null
  error: unknown
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  counts: RequestCounts | null
  options: FilterOptions
  reload: () => Promise<void>
  more: () => Promise<void>
}

const filterArgs = (filters: RequestFilters) => ({
  search: filters.search || null,
  reference_doctype: filters.reference_doctype || null,
  sender: filters.sender || null,
  date_from: filters.date_from || null,
  date_to: filters.date_to || null,
})

export function useRequests(tab: Ref<Tab>, filters: Ref<RequestFilters>): RequestList {
  let run = 0
  const state = reactive<RequestList>({
    data: null,
    error: null,
    loading: false,
    loadingMore: false,
    hasMore: false,
    counts: null,
    options: { doctypes: [], senders: [] },
    reload,
    more,
  })

  async function reload() {
    const mine = ++run
    state.loading = true
    state.error = null
    try {
      const args = filterArgs(filters.value)
      const [page, counts] = await Promise.all([
        staff<{ rows: RequestRow[]; has_more: boolean }>('list_requests', { status: tab.value, ...args }),
        staff<RequestCounts>('request_counts', args),
      ])
      if (mine !== run) return
      state.data = page.rows
      state.hasMore = page.has_more
      state.counts = counts
    } catch (error) {
      if (mine === run) state.error = error
    } finally {
      if (mine === run) state.loading = false
    }
  }

  async function more() {
    if (!state.data || !state.hasMore || state.loadingMore) return
    const mine = run
    state.loadingMore = true
    try {
      const page = await staff<{ rows: RequestRow[]; has_more: boolean }>('list_requests', {
        status: tab.value,
        ...filterArgs(filters.value),
        start: state.data.length,
      })
      if (mine !== run || !state.data) return
      state.data = [...state.data, ...page.rows]
      state.hasMore = page.has_more
    } finally {
      state.loadingMore = false
    }
  }

  watch([tab, filters], () => void reload(), { deep: true, immediate: true })
  void staff<FilterOptions>('request_filter_options').then((options) => (state.options = options))
  return state
}

export const emptyFilters = (): RequestFilters => ({
  search: '',
  reference_doctype: '',
  sender: '',
  date_from: '',
  date_to: '',
})

export function hasFilters(filters: RequestFilters): boolean {
  return Object.values(filters).some(Boolean)
}
