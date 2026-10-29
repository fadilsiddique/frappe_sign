// The main action and the menu of a request, from its state (UX_PLAN "Sent" and "Request detail").
// Shared by the Sent preview and the request page.
import type { DropdownItem } from 'frappe-ui'
import { computed, type Ref } from 'vue'
import { __ } from '@/shared/translate'
import { downloadUrl, type useRequestActions } from './useRequestActions'

export interface RequestState {
  name: string
  status: string
  can_write: boolean
  original_sha256?: string | null
  signed_sha256?: string | null
  sealing_state?: string | null
}

export interface PrimaryAction {
  label: string
  icon: string
  run?: () => unknown
  href?: string
  route?: string
}

export function useRequestView(
  state: Ref<RequestState | null>,
  actions: ReturnType<typeof useRequestActions>,
) {
  const open = computed(() => ['Sent', 'In Progress'].includes(state.value?.status ?? ''))

  const primary = computed<PrimaryAction | null>(() => {
    const request = state.value
    if (!request || (!request.can_write && request.status !== 'Completed')) return null
    if (request.status === 'Draft')
      return { label: __('Send'), icon: 'lucide-send', run: () => actions.send(request.name) }
    if (open.value)
      return { label: __('Remind'), icon: 'lucide-bell', run: () => actions.remind(request.name) }
    if (request.status === 'Completed')
      return {
        label: __('Download signed PDF'),
        icon: 'lucide-download',
        href: downloadUrl(request.name, 'signed'),
      }
    return { label: __('Send again'), icon: 'lucide-send', route: '/new' }
  })

  const menu = computed<DropdownItem[]>(() => {
    const request = state.value
    if (!request) return []
    const items: DropdownItem[] = []
    const go = (url: string) => () => (window.location.href = url)
    if (request.original_sha256)
      items.push({
        label: __('Original PDF'),
        icon: 'lucide-file',
        onClick: go(downloadUrl(request.name, 'original')),
      })
    if (request.signed_sha256) {
      items.push({
        label: __('Certificate'),
        icon: 'lucide-award',
        onClick: go(downloadUrl(request.name, 'certificate')),
      })
      if (request.status !== 'Completed')
        items.push({
          label: __('Signed PDF'),
          icon: 'lucide-download',
          onClick: go(downloadUrl(request.name, 'signed')),
        })
    }
    if (request.sealing_state === 'Failed' && request.can_write)
      items.push({
        label: __('Retry seal'),
        icon: 'lucide-rotate-cw',
        onClick: () => actions.retrySeal(request.name),
      })
    if (open.value && request.can_write)
      items.push({
        label: __('Void request'),
        icon: 'lucide-ban',
        theme: 'red',
        onClick: () => actions.voidRequest(request.name),
      })
    return items
  })

  return { open, primary, menu }
}
