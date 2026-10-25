// Template designer state (DESIGN 7.4): roles, fields as normalized rects, selection, undo/redo.
// The saved payload goes to frappe_sign.api.staff.save_template unchanged, and the server overlay
// draws each field at the same rect (tests/designer-roundtrip.test.ts and the Python round trip).
import { defineStore } from 'pinia'
import { clampRect, displaySize, pixelsToNormalized, type PageMetric, type Rect } from '@/shared/coords'
import { dragRect, nudge, pageSteps, type Handle, type Viewport } from '@/shared/composables/useDragResize'

export type FieldType =
  | 'Signature'
  | 'Initials'
  | 'Full Name'
  | 'Email'
  | 'Date Signed'
  | 'Text'
  | 'Number'
  | 'Checkbox'
  | 'Dropdown'
  | 'Company Stamp'
  | 'Attachment'

export const FIELD_TYPES: FieldType[] = [
  'Signature',
  'Initials',
  'Full Name',
  'Email',
  'Date Signed',
  'Text',
  'Number',
  'Checkbox',
  'Dropdown',
  'Company Stamp',
  'Attachment',
]

// Default size of a new field in PDF points.
export const DEFAULT_SIZE: Record<FieldType, [number, number]> = {
  Signature: [160, 48],
  Initials: [64, 40],
  'Full Name': [160, 20],
  Email: [160, 20],
  'Date Signed': [100, 20],
  Text: [160, 20],
  Number: [100, 20],
  Checkbox: [14, 14],
  Dropdown: [140, 20],
  'Company Stamp': [96, 96],
  Attachment: [140, 20],
}

export const ROLE_COLORS = ['#0f766e', '#7c3aed', '#c2410c', '#2563eb', '#be123c', '#4d7c0f']

export interface DesignerRole {
  role_label: string
  routing_order: number
  kind: 'Signer' | 'Approver' | 'CC'
  signer_source: 'Fixed User' | 'Doc Field' | 'Party Contact' | 'Employee' | 'Ask at Send'
  source_field?: string | null
  fixed_user?: string | null
  can_delegate: 0 | 1
  color: string
}

export interface DesignerField {
  field_key: string
  role_label: string
  field_type: FieldType
  page: number
  x: number
  y: number
  w: number
  h: number
  required: 0 | 1
  read_only: 0 | 1
  prefill_path?: string | null
  options?: string | null
  font_size: number
  validation_regex?: string | null
  anchor_tag?: string | null
}

interface Snapshot {
  roles: DesignerRole[]
  fields: DesignerField[]
}

const HISTORY_LIMIT = 100

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function slug(value: string): string {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_|_$/g, '') || 'field'
  )
}

export const useDesigner = defineStore('frappe-sign-designer', {
  state: () => ({
    name: null as string | null,
    title: '',
    signingOrder: 'Sequential' as 'Sequential' | 'Parallel',
    otpMode: 'Off' as 'Off' | 'Email' | 'WhatsApp',
    pages: [] as PageMetric[],
    roles: [] as DesignerRole[],
    fields: [] as DesignerField[],
    selected: [] as string[],
    activeRole: '' as string,
    past: [] as Snapshot[],
    future: [] as Snapshot[],
    dirty: false,
  }),

  getters: {
    roleColor: (state) => (label: string) =>
      state.roles.find((role) => role.role_label === label)?.color ?? ROLE_COLORS[0],
    fieldsOn: (state) => (page: number) => state.fields.filter((field) => field.page === page),
    selection: (state) => state.fields.filter((field) => state.selected.includes(field.field_key)),
    canUndo: (state) => state.past.length > 0,
    canRedo: (state) => state.future.length > 0,
    signerRoles: (state) => state.roles.filter((role) => role.kind === 'Signer'),
  },

  actions: {
    load(template: {
      name?: string | null
      title?: string
      signing_order?: string
      otp_mode?: string
      page_metrics?: string | PageMetric[] | null
      roles?: Partial<DesignerRole>[]
      fields?: Partial<DesignerField>[]
    }) {
      this.name = template.name ?? null
      this.title = template.title ?? ''
      this.signingOrder = template.signing_order === 'Parallel' ? 'Parallel' : 'Sequential'
      this.otpMode = (template.otp_mode as 'Off' | 'Email' | 'WhatsApp') ?? 'Off'
      const metrics = template.page_metrics
      this.pages = typeof metrics === 'string' ? (JSON.parse(metrics) as PageMetric[]) : (metrics ?? [])
      this.roles = (template.roles ?? []).map((role, index) => ({
        role_label: role.role_label ?? `Signer ${index + 1}`,
        routing_order: role.routing_order ?? index + 1,
        kind: role.kind ?? 'Signer',
        signer_source: role.signer_source ?? 'Ask at Send',
        source_field: role.source_field ?? null,
        fixed_user: role.fixed_user ?? null,
        can_delegate: role.can_delegate ? 1 : 0,
        color: role.color || ROLE_COLORS[index % ROLE_COLORS.length],
      }))
      this.fields = (template.fields ?? []).map((field) => ({
        field_key: field.field_key!,
        role_label: field.role_label!,
        field_type: field.field_type!,
        page: field.page ?? 1,
        x: field.x ?? 0,
        y: field.y ?? 0,
        w: field.w ?? 0.1,
        h: field.h ?? 0.03,
        required: field.required === 0 ? 0 : 1,
        read_only: field.read_only ? 1 : 0,
        prefill_path: field.prefill_path ?? null,
        options: field.options ?? null,
        font_size: field.font_size || 11,
        validation_regex: field.validation_regex ?? null,
        anchor_tag: field.anchor_tag ?? null,
      }))
      this.activeRole = this.signerRoles[0]?.role_label ?? ''
      this.selected = []
      this.past = []
      this.future = []
      this.dirty = false
    },

    setPages(pages: PageMetric[]) {
      this.pages = pages
    },

    record() {
      this.past.push(clone({ roles: this.roles, fields: this.fields }))
      if (this.past.length > HISTORY_LIMIT) this.past.shift()
      this.future = []
      this.dirty = true
    },

    undo() {
      const previous = this.past.pop()
      if (!previous) return
      this.future.push(clone({ roles: this.roles, fields: this.fields }))
      this.roles = previous.roles
      this.fields = previous.fields
      this.selected = this.selected.filter((key) => this.fields.some((f) => f.field_key === key))
      this.dirty = true
    },

    redo() {
      const next = this.future.pop()
      if (!next) return
      this.past.push(clone({ roles: this.roles, fields: this.fields }))
      this.roles = next.roles
      this.fields = next.fields
      this.dirty = true
    },

    addRole(kind: DesignerRole['kind'] = 'Signer') {
      this.record()
      const index = this.roles.length
      let label = kind === 'Signer' ? `Signer ${index + 1}` : `${kind} ${index + 1}`
      while (this.roles.some((role) => role.role_label === label)) label += '+'
      this.roles.push({
        role_label: label,
        routing_order: index + 1,
        kind,
        signer_source: 'Ask at Send',
        can_delegate: 0,
        color: ROLE_COLORS[index % ROLE_COLORS.length],
      })
      if (kind === 'Signer' && !this.activeRole) this.activeRole = label
      return label
    },

    updateRole(label: string, patch: Partial<DesignerRole>) {
      const role = this.roles.find((r) => r.role_label === label)
      if (!role) return
      this.record()
      if (patch.role_label && patch.role_label !== label) {
        for (const field of this.fields) if (field.role_label === label) field.role_label = patch.role_label
        if (this.activeRole === label) this.activeRole = patch.role_label
      }
      Object.assign(role, patch)
    },

    removeRole(label: string) {
      this.record()
      this.roles = this.roles.filter((role) => role.role_label !== label)
      this.fields = this.fields.filter((field) => field.role_label !== label)
      if (this.activeRole === label) this.activeRole = this.signerRoles[0]?.role_label ?? ''
    },

    newKey(type: FieldType, role: string): string {
      const base = `${slug(role)}_${slug(type)}`
      let n = 1
      while (this.fields.some((field) => field.field_key === `${base}_${n}`)) n++
      return `${base}_${n}`
    },

    // Drop a new field with its top-left corner at (px, py) on a page drawn at `viewport` size.
    placeField(type: FieldType, page: number, px: number, py: number, viewport: Viewport): DesignerField {
      const metric = this.pages.find((m) => m.page === page)
      if (!metric) throw new Error(`No page ${page}`)
      const role = this.activeRole || this.signerRoles[0]?.role_label || this.addRole('Signer')
      const size = displaySize(metric)
      const [w, h] = DEFAULT_SIZE[type]
      const start = pixelsToNormalized({ x: px, y: py, w: 0, h: 0 }, viewport.width, viewport.height)
      const steps = pageSteps(metric)
      const rect = dragRect(
        clampRect({ x: start.x, y: start.y, w: w / size.width, h: h / size.height }, 0),
        'move',
        0,
        0,
        viewport,
        steps,
      )
      this.record()
      const field: DesignerField = {
        field_key: this.newKey(type, role),
        role_label: role,
        field_type: type,
        page,
        ...rect,
        required: type === 'Checkbox' ? 0 : 1,
        read_only: 0,
        options: type === 'Dropdown' ? 'Option 1\nOption 2' : null,
        font_size: 11,
      }
      this.fields.push(field)
      this.selected = [field.field_key]
      return field
    },

    // Move or resize one field, given the drag from its rect when the drag began.
    dragField(key: string, start: Rect, handle: Handle, dx: number, dy: number, viewport: Viewport) {
      const field = this.fields.find((f) => f.field_key === key)
      const metric = field && this.pages.find((m) => m.page === field.page)
      if (!field || !metric) return
      Object.assign(field, dragRect(start, handle, dx, dy, viewport, pageSteps(metric)))
      this.dirty = true
    },

    updateField(key: string, patch: Partial<DesignerField>) {
      const field = this.fields.find((f) => f.field_key === key)
      if (!field) return
      this.record()
      Object.assign(field, patch)
    },

    select(key: string, additive = false) {
      if (!additive) this.selected = [key]
      else if (this.selected.includes(key)) this.selected = this.selected.filter((k) => k !== key)
      else this.selected.push(key)
    },

    clearSelection() {
      this.selected = []
    },

    removeSelected() {
      if (!this.selected.length) return
      this.record()
      this.fields = this.fields.filter((field) => !this.selected.includes(field.field_key))
      this.selected = []
    },

    nudgeSelected(key: string, big = false) {
      if (!this.selected.length) return
      this.record()
      for (const field of this.selection) {
        const metric = this.pages.find((m) => m.page === field.page)
        if (metric) Object.assign(field, nudge(field, key, pageSteps(metric), big))
      }
    },

    duplicateToAllPages(key: string) {
      const source = this.fields.find((f) => f.field_key === key)
      if (!source) return
      this.record()
      for (const metric of this.pages) {
        if (metric.page === source.page) continue
        this.fields.push({
          ...clone(source),
          page: metric.page,
          field_key: this.newKey(source.field_type, source.role_label),
        })
      }
    },

    // What save_template receives: the template settings, roles and fields.
    payload() {
      return {
        title: this.title,
        signing_order: this.signingOrder,
        otp_mode: this.otpMode,
        roles: this.roles.map((role) => ({ ...role })),
        fields: this.fields.map((field) => ({ ...field })),
      }
    },
  },
})
