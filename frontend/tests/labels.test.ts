import { describe, expect, it } from 'vitest'
import {
  otpModeLabel,
  requestStatus,
  roleKindLabel,
  signerSourceLabel,
  signingOrderLabel,
} from '@/staff/labels'

describe('requestStatus', () => {
  it.each([
    ['Sent', undefined, undefined, 'Waiting', 'blue'],
    ['In Progress', 'Not Started', undefined, 'Waiting', 'blue'],
    ['Completed', 'Sealed', undefined, 'Completed', 'green'],
    ['Draft', undefined, undefined, 'Draft', 'gray'],
    ['Declined', undefined, undefined, 'Declined', 'red'],
    ['Voided', undefined, undefined, 'Voided', 'gray'],
    ['Expired', undefined, undefined, 'Expired', 'amber'],
  ])('%s shows as %s', (status, sealing, sending, label, theme) => {
    expect(requestStatus(status, sealing, sending)).toEqual({ label, theme })
  })

  it('shows sending and send failures on drafts', () => {
    expect(requestStatus('Draft', undefined, 'Queued')).toEqual({ label: 'Sending', theme: 'blue' })
    expect(requestStatus('Draft', undefined, 'Failed')).toEqual({ label: 'Send failed', theme: 'red' })
  })

  it('shows sealing while the seal job runs, and its failure', () => {
    expect(requestStatus('In Progress', 'Queued')).toEqual({ label: 'Sealing', theme: 'blue' })
    expect(requestStatus('In Progress', 'Sealing')).toEqual({ label: 'Sealing', theme: 'blue' })
    expect(requestStatus('In Progress', 'Failed')).toEqual({ label: 'Seal failed', theme: 'red' })
  })

  it('keeps an unknown status as it is', () => {
    expect(requestStatus('Archived')).toEqual({ label: 'Archived', theme: 'gray' })
  })
})

describe('people words', () => {
  it('names what each role does', () => {
    expect(roleKindLabel('Signer')).toBe('Signs')
    expect(roleKindLabel('Approver')).toBe('Approves')
    expect(roleKindLabel('CC')).toBe('Gets a copy')
  })

  it('says who signs in plain words', () => {
    expect(signerSourceLabel('Ask at Send')).toBe('Chosen when sending')
    expect(signerSourceLabel('Fixed User')).toBe('A specific person')
    expect(signerSourceLabel('Doc Field')).toBe('A person named in a field of the document')
    expect(signerSourceLabel('Party Contact')).toBe('The customer or supplier on the document')
    expect(signerSourceLabel('Employee')).toBe('The employee on the document')
  })

  it('names the signing order and the emailed code', () => {
    expect(signingOrderLabel('Sequential')).toBe('Sign in this order')
    expect(signingOrderLabel('Parallel')).toBe('All at once')
    expect(otpModeLabel('Email')).toBe('On')
    expect(otpModeLabel('Off')).toBe('Off')
  })

  it('keeps an unknown value as it is', () => {
    expect(roleKindLabel('Witness')).toBe('Witness')
    expect(signerSourceLabel('Script')).toBe('Script')
  })
})
