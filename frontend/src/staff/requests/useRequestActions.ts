// The sender's actions on one request, shared by the Sent preview and the detail page (U.5):
// remind, void (with a reason), a new link, send a draft and retry the seal.
import { dialog, toast } from 'frappe-ui'
import { __ } from '@/shared/translate'
import { errorMessage, STAFF_API, staff } from '../api'

export function downloadUrl(envelope: string, kind: 'original' | 'signed' | 'certificate'): string {
  return `/api/method/${STAFF_API}download?envelope=${encodeURIComponent(envelope)}&kind=${kind}`
}

export function useRequestActions(done: () => unknown) {
  async function act(method: string, args: Record<string, unknown>, message: string): Promise<boolean> {
    try {
      await staff(method, args)
      toast.success(message)
      await done()
      return true
    } catch (error) {
      toast.error(errorMessage(error))
      return false
    }
  }

  return {
    remind: (envelope: string, recipient?: string) =>
      act('remind', { envelope, ...(recipient ? { recipient } : {}) }, __('Reminder sent')),
    send: (envelope: string) => act('send_envelope', { envelope }, __('Sending')),
    retrySeal: (envelope: string) => act('retry_seal', { envelope }, __('Sealing queued')),
    voidRequest(envelope: string) {
      dialog.prompt({
        title: __('Void this request?'),
        message: __('Nobody can sign it after this. Everyone who was waiting will see that it was voided.'),
        theme: 'red',
        confirmLabel: __('Void request'),
        fields: [
          {
            name: 'reason',
            type: 'textarea',
            label: __('Reason'),
            placeholder: __('Why are you voiding it?'),
            required: true,
          },
        ],
        onConfirm: async ({ values }) => {
          await staff('void_envelope', { envelope, reason: String(values.reason).trim() })
          toast.success(__('Request voided'))
          await done()
        },
      })
    },
    newLink(envelope: string, recipient: string, email: string) {
      dialog.prompt({
        title: __('Send a new link'),
        message: __('The old link stops working. Check the email address if it was wrong.'),
        confirmLabel: __('Send link'),
        fields: [{ name: 'email', label: __('Email'), defaultValue: email, required: true }],
        onConfirm: async ({ values }) => {
          await staff('resend', { envelope, recipient, email: String(values.email).trim() })
          toast.success(__('New link sent'))
          await done()
        },
      })
    },
  }
}
