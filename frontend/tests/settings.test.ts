import { flushPromises, mount } from '@vue/test-utils'
import { FormControl } from 'frappe-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProfileCard from '@/staff/settings/ProfileCard.vue'
import DocumentsTab from '@/staff/settings/DocumentsTab.vue'
import SigningTab from '@/staff/settings/SigningTab.vue'
import { consentToHtml, consentToText, sealLine, senderLine, sendsLine } from '@/staff/settings/lines'
import type { ProfileCard as Profile, SettingsData } from '@/staff/settings/types'
import { visibleNavItems } from '@/staff/shell/nav'

const staff = vi.fn()
vi.mock('@/staff/api', async (original) => ({
  ...(await original<typeof import('@/staff/api')>()),
  staff: (method: string, args: unknown) => staff(method, args),
}))

const profile: Profile = {
  company: 'Gulf Trading LLC',
  logo: null,
  brand_color: '#0f766e',
  legal_footer: null,
  sender_email_account: null,
  authorised_signatory: null,
  seal: { kind: 'Self-signed', valid_to: '2029-10-24', expired: false },
  sender: { status: 'default', email_id: 'sign@gulftrading.ae' },
}

const data = (overrides: Partial<SettingsData> = {}): SettingsData => ({
  can_edit: true,
  has_erpnext: true,
  profiles: [profile],
  companies: [],
  email_accounts: [{ name: 'Sales', email_id: 'sales@gulftrading.ae' }],
  signatories: [{ name: 'mariam@gulftrading.ae', full_name: 'Mariam Haddad' }],
  documents: [
    {
      doctype: 'Quotation',
      default_template: null,
      templates: [{ name: 'STPL-1', title: 'Quotation for signature' }],
      sends: 3,
    },
  ],
  signing: {
    default_expiry_days: 14,
    default_reminder_days: 3,
    otp_validity_minutes: 10,
    consent_text: null,
  },
  advanced: { tsa_urls: '', max_upload_mb: 20, max_pages: 200 },
  ...overrides,
})

beforeEach(() => {
  document.documentElement.lang = 'en-GB'
  staff.mockReset()
  staff.mockResolvedValue({})
})

describe('settings words', () => {
  it('words the seal', () => {
    expect(sealLine(profile.seal)).toEqual({ text: 'Self-signed, valid until 24 Oct 2029', tone: 'ok' })
    expect(sealLine({ kind: null, valid_to: null, expired: false }).tone).toBe('bad')
    expect(sealLine({ kind: 'Self-signed', valid_to: '2025-01-02', expired: true }).text).toMatch(
      /^Expired on 2 Jan/,
    )
  })

  it('words the sender', () => {
    expect(senderLine({ status: 'connected', email_id: 'a@b.c' }).text).toBe('Connected: a@b.c')
    expect(senderLine({ status: 'missing', email_id: null }).tone).toBe('bad')
  })

  it('counts sends', () => {
    expect([sendsLine(0), sendsLine(1), sendsLine(5)]).toEqual(['Not sent yet', '1 request', '5 requests'])
  })

  it('round trips the consent text between plain text and HTML', () => {
    const html = consentToHtml('First <b>line</b>\nsecond\n\nNew paragraph & more')
    expect(html).toBe('<p>First &lt;b&gt;line&lt;/b&gt;<br>second</p><p>New paragraph &amp; more</p>')
    expect(consentToText(html)).toBe('First <b>line</b>\nsecond\n\nNew paragraph & more')
    expect(consentToText(null)).toBe('')
  })

  it('hides Settings from people who are not managers', () => {
    expect(visibleNavItems(false).map((i) => i.key)).not.toContain('settings')
    expect(visibleNavItems(true).map((i) => i.key)).toContain('settings')
  })
})

describe('ProfileCard', () => {
  it('saves only when something changed, with the new values', async () => {
    const wrapper = mount(ProfileCard, { props: { profile, data: data() } })
    const save = wrapper.get('[data-testid="save-profile"]')
    expect(save.attributes('disabled')).toBeDefined()
    await wrapper
      .get('[data-testid="brand-color"] input, input[data-testid="brand-color"]')
      .setValue('#112233')
    await save.trigger('click')
    await flushPromises()
    expect(staff).toHaveBeenCalledWith('save_profile', {
      company: 'Gulf Trading LLC',
      values: expect.objectContaining({ brand_color: '#112233' }),
    })
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('offers a test seal only when there is no valid one', async () => {
    const valid = mount(ProfileCard, { props: { profile, data: data() } })
    expect(valid.find('[data-testid="create-test-seal"]').exists()).toBe(false)
    expect(valid.get('[data-testid="open-seal-dialog"]').text()).toContain('Replace certificate')

    const missing = { ...profile, seal: { kind: null, valid_to: null, expired: false } }
    const wrapper = mount(ProfileCard, { props: { profile: missing, data: data() } })
    expect(wrapper.get('[data-testid="seal-status"]').text()).toContain('Missing')
    await wrapper.get('[data-testid="create-test-seal"]').trigger('click')
    await flushPromises()
    expect(staff).toHaveBeenCalledWith('create_test_certificate', {
      company: 'Gulf Trading LLC',
      common_name: 'Gulf Trading LLC',
      replace: true,
    })
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('is read only for a Sign Manager', () => {
    const wrapper = mount(ProfileCard, { props: { profile, data: data({ can_edit: false }) } })
    expect(wrapper.find('[data-testid="save-profile"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="open-seal-dialog"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="seal-status"]').text()).toContain('valid until 24 Oct 2029')
  })
})

describe('DocumentsTab', () => {
  it('shows each type with its sends and sets the default template', async () => {
    const wrapper = mount(DocumentsTab, { props: { data: data() } })
    const row = wrapper.get('[data-testid="document-Quotation"]')
    expect(row.text()).toContain('3 requests')
    // frappe-ui's select is a combobox, not a <select>: act on the control itself.
    row.findComponent(FormControl).vm.$emit('update:modelValue', 'STPL-1')
    await flushPromises()
    expect(staff).toHaveBeenCalledWith('set_default_template', { doctype: 'Quotation', template: 'STPL-1' })
  })

  it('has no controls for a Sign Manager', () => {
    const wrapper = mount(DocumentsTab, { props: { data: data({ can_edit: false }) } })
    expect(wrapper.find('[data-testid="add-document"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="remove-document"]').exists()).toBe(false)
  })

  it('says what to do on an empty list', () => {
    const wrapper = mount(DocumentsTab, { props: { data: data({ documents: [] }) } })
    expect(wrapper.get('[data-testid="empty-state"]').text()).toContain('No document type yet')
  })
})

describe('SigningTab', () => {
  it('saves the consent as HTML and the numbers as given', async () => {
    const wrapper = mount(SigningTab, { props: { data: data() } })
    await wrapper
      .get('[data-testid="consent-text"] textarea, textarea[data-testid="consent-text"]')
      .setValue('I agree.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(staff).toHaveBeenCalledWith('save_settings', {
      section: 'signing',
      values: {
        default_expiry_days: '14',
        default_reminder_days: '3',
        otp_validity_minutes: '10',
        consent_text: '<p>I agree.</p>',
      },
    })
  })
})
