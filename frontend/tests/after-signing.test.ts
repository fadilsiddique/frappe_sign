import { describe, expect, it } from 'vitest'
import {
  afterFromStored,
  afterOptions,
  afterProblem,
  afterToStored,
  emptyAfter,
  SALES_ORDER_METHOD,
} from '@/staff/templates/afterSigning'

describe('after everyone signs', () => {
  it('builds the stored action for each choice', () => {
    expect(afterToStored(emptyAfter())).toEqual({ action: 'None', config: {} })
    expect(afterToStored({ ...emptyAfter(), choice: 'submit' })).toEqual({ action: 'Submit', config: {} })
    expect(afterToStored({ ...emptyAfter(), choice: 'sales_order' })).toEqual({
      action: 'Create Mapped Document',
      config: { method: SALES_ORDER_METHOD, save: 1 },
    })
    expect(
      afterToStored({ ...emptyAfter(), choice: 'set_field', fieldname: 'status', value: 'Signed' }),
    ).toEqual({ action: 'Set Field Value', config: { fieldname: 'status', value: 'Signed' } })
    expect(afterToStored({ ...emptyAfter(), choice: 'workflow', workflowAction: 'Approve' })).toEqual({
      action: 'Apply Workflow Action',
      config: { action: 'Approve' },
    })
  })

  it('reads back what it built, from a string or an object config', () => {
    const stored = afterToStored({
      ...emptyAfter(),
      choice: 'set_field',
      fieldname: 'status',
      value: 'Signed',
    })
    const back = afterFromStored(stored.action, JSON.stringify(stored.config))
    expect(back).toMatchObject({ choice: 'set_field', fieldname: 'status', value: 'Signed' })
    expect(afterFromStored('Create Mapped Document', { method: SALES_ORDER_METHOD, save: 1 }).choice).toBe(
      'sales_order',
    )
    expect(afterFromStored(null, null).choice).toBe('none')
  })

  it('keeps a setting it cannot show', () => {
    const state = afterFromStored('Call Method', '{"method":"app.api.go"}')
    expect(state.choice).toBe('custom')
    expect(afterToStored(state)).toEqual({ action: 'Call Method', config: { method: 'app.api.go' } })
    const mapped = afterFromStored('Create Mapped Document', { method: 'other.make', save: 1 })
    expect(mapped.choice).toBe('custom')
  })

  it('offers the Sales Order only for a Quotation', () => {
    expect(afterOptions('Quotation', 'none').map((o) => o.value)).toContain('sales_order')
    expect(afterOptions('Sales Invoice', 'none').map((o) => o.value)).not.toContain('sales_order')
  })

  it('says what is missing', () => {
    expect(afterProblem({ ...emptyAfter(), choice: 'set_field' })).not.toBe('')
    expect(afterProblem({ ...emptyAfter(), choice: 'workflow' })).not.toBe('')
    expect(afterProblem({ ...emptyAfter(), choice: 'submit' })).toBe('')
  })
})
