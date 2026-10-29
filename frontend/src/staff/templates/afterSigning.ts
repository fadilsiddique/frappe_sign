// "After everyone signs": a short list of choices that builds the template's post_sign_action and
// post_sign_config (DESIGN 4.6), so nobody writes JSON. A setting made in Desk that the list cannot
// show is kept as it is ("custom").
import { __ } from '@/shared/translate'

export type AfterChoice = 'none' | 'submit' | 'sales_order' | 'set_field' | 'workflow' | 'custom'

export interface AfterState {
  choice: AfterChoice
  fieldname: string
  value: string
  workflowAction: string
  // The stored action and config, only for "custom".
  action: string
  config: Record<string, unknown>
}

export interface AfterStored {
  action: string
  config: Record<string, unknown>
}

export const SALES_ORDER_METHOD = 'erpnext.selling.doctype.quotation.quotation.make_sales_order'

export function emptyAfter(): AfterState {
  return { choice: 'none', fieldname: '', value: '', workflowAction: '', action: 'None', config: {} }
}

export function afterToStored(state: AfterState): AfterStored {
  switch (state.choice) {
    case 'submit':
      return { action: 'Submit', config: {} }
    case 'sales_order':
      return { action: 'Create Mapped Document', config: { method: SALES_ORDER_METHOD, save: 1 } }
    case 'set_field':
      return { action: 'Set Field Value', config: { fieldname: state.fieldname, value: state.value } }
    case 'workflow':
      return { action: 'Apply Workflow Action', config: { action: state.workflowAction } }
    case 'custom':
      return { action: state.action, config: state.config }
    default:
      return { action: 'None', config: {} }
  }
}

export function afterFromStored(action: string | null, rawConfig: unknown): AfterState {
  const state = emptyAfter()
  const config = parseConfig(rawConfig)
  if (!action || action === 'None') return state
  if (action === 'Submit') return { ...state, choice: 'submit' }
  if (action === 'Create Mapped Document' && config.method === SALES_ORDER_METHOD && config.save !== 0)
    return { ...state, choice: 'sales_order' }
  if (action === 'Set Field Value')
    return {
      ...state,
      choice: 'set_field',
      fieldname: String(config.fieldname ?? ''),
      value: String(config.value ?? ''),
    }
  if (action === 'Apply Workflow Action')
    return { ...state, choice: 'workflow', workflowAction: String(config.action ?? '') }
  return { ...state, choice: 'custom', action, config }
}

function parseConfig(raw: unknown): Record<string, unknown> {
  if (!raw) return {}
  if (typeof raw !== 'string') return raw as Record<string, unknown>
  try {
    return JSON.parse(raw) as Record<string, unknown>
  } catch {
    return {}
  }
}

export interface AfterOption {
  value: AfterChoice
  label: string
}

// The choices shown for a DocType. "Create a draft Sales Order" is only for a Quotation.
export function afterOptions(doctype: string, current: AfterChoice): AfterOption[] {
  const options: AfterOption[] = [
    { value: 'none', label: __('Do nothing') },
    { value: 'submit', label: __('Submit the document') },
  ]
  if (doctype === 'Quotation' || current === 'sales_order')
    options.push({ value: 'sales_order', label: __('Create a draft Sales Order') })
  options.push(
    { value: 'set_field', label: __('Set a field') },
    { value: 'workflow', label: __('Apply a workflow action') },
  )
  if (current === 'custom')
    options.push({ value: 'custom', label: __('Custom setting from Desk (kept as it is)') })
  return options
}

// What is missing before the choice can be saved, or an empty string.
export function afterProblem(state: AfterState): string {
  if (state.choice === 'set_field' && !state.fieldname) return __('Pick the field to set.')
  if (state.choice === 'workflow' && !state.workflowAction.trim()) return __('Type the workflow action.')
  return ''
}
