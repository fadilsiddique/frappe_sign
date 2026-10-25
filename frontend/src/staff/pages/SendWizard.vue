<script setup lang="ts">
// Send wizard (P1.17, P2.9): source (published template, uploaded PDF, or a document rendered with
// its Print Format), recipients, fields (for an uploaded PDF, placed with the designer canvas),
// preview (for a document: the anchors sign_field() placed and the prefilled values), review, send.
// Desk's "Customize" opens it with ?doctype=&name=&template=&print_format=&letter_head=.
import { Button, call, createListResource, FormControl, toast } from 'frappe-ui'
import { computed, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { PageMetric } from '@/shared/coords'
import { __ } from '@/shared/translate'
import { errorMessage, fetchPdf, fileToBase64, STAFF_API, staff } from '../api'
import AnchorPreview, { type PreviewAnchor } from '../components/AnchorPreview.vue'
import AppPageHeader from '../components/AppPageHeader.vue'
import { otpModeLabel, roleKindLabel, signingOrderLabel } from '../labels'
import DesignerCanvas from '../designer/DesignerCanvas.vue'
import RolesPanel from '../designer/RolesPanel.vue'
import { FIELD_TYPES, useDesigner, type FieldType } from '../designer/store'

type Step = 'source' | 'recipients' | 'fields' | 'preview' | 'review'
interface Recipient {
  role_label: string
  kind: string
  routing_order: number
  full_name: string
  email: string
  mobile?: string | null
  party_type?: string | null
  party?: string | null
  contact?: string | null
  resolved?: boolean
}
interface DocumentTemplate {
  name: string
  title: string
  print_format: string | null
  letter_head: string | null
}
interface Preview {
  key: string
  generator: string
  generator_tested: boolean
  metrics: PageMetric[]
  anchors: PreviewAnchor[]
}
interface Prefill {
  field_key: string
  role_label: string
  field_type: string
  read_only: number
  value: string
}

const route = useRoute()
const router = useRouter()
const store = useDesigner()
const step = ref<Step>('source')
const mode = ref<'template' | 'upload' | 'document'>('template')
const doc = reactive({ doctype: '', name: '', template: '', printFormat: '', letterHead: '' })
const documentTemplates = ref<DocumentTemplate[]>([])
const preview = shallowRef<Preview | null>(null)
const prefill = ref<Prefill[]>([])
const templateVersion = ref('')
const sourceFile = ref('')
const pdf = shallowRef<ArrayBuffer | null>(null)
const placing = ref<FieldType | null>(null)
const busy = ref(false)
const form = reactive({ title: '', message: '', signingOrder: 'Sequential', otpMode: 'Off' })
const recipients = ref<Recipient[]>([])

const templates = createListResource({
  doctype: 'Sign Template',
  fields: ['name', 'title', 'published_version', 'source_type', 'reference_doctype'],
  filters: { published_version: ['is', 'set'], is_active: 1 },
  orderBy: 'title asc',
  pageLength: 200,
  auto: true,
})

const steps = computed<Step[]>(() => {
  if (mode.value === 'upload') return ['source', 'recipients', 'fields', 'review']
  if (mode.value === 'document') return ['source', 'recipients', 'preview', 'review']
  return ['source', 'recipients', 'review']
})

// Anchor roles are role labels with spaces as underscores (pdf/anchors.py role_token).
const signerTokens = computed(() =>
  recipients.value.filter((r) => r.kind === 'Signer').map((r) => r.role_label.trim().split(/\s+/).join('_')),
)

async function chooseTemplate(
  name: string,
  version: string,
  title: string,
  sourceType?: string,
  doctype?: string,
) {
  if (sourceType === 'Print Format' && doctype) {
    // A Print Format template needs the document to render.
    doc.doctype = doctype
    doc.template = name
    toast.info(__('Choose the {0} to send.', [__(doctype)]))
    return
  }
  busy.value = true
  try {
    const snapshot = await call<{ snapshot: string }>('frappe.client.get_value', {
      doctype: 'Sign Template Version',
      filters: version,
      fieldname: 'snapshot',
    })
    const parsed = JSON.parse(snapshot.snapshot) as {
      roles: Recipient[]
      signing_order: string
      otp_mode: string
    }
    templateVersion.value = version
    form.title = form.title || title
    recipients.value = parsed.roles.map((role) => ({ ...role, full_name: '', email: '' }))
    mode.value = 'template'
    step.value = 'recipients'
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

async function loadDocument() {
  if (!doc.doctype || !doc.name) return
  busy.value = true
  try {
    documentTemplates.value = await staff<DocumentTemplate[]>('document_templates', { doctype: doc.doctype })
    if (!documentTemplates.value.length) {
      toast.error(__('Publish a template for {0} first.', [__(doc.doctype)]))
      return
    }
    if (!documentTemplates.value.some((t) => t.name === doc.template))
      doc.template = documentTemplates.value[0].name
    await loadTemplate()
    form.title = form.title || `${__(doc.doctype)} ${doc.name}`
    mode.value = 'document'
    step.value = 'recipients'
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

async function loadTemplate() {
  const chosen = documentTemplates.value.find((t) => t.name === doc.template)
  const target = { doctype: doc.doctype, name: doc.name }
  const [rows, rendered, values] = await Promise.all([
    staff<Recipient[]>('resolve_recipients', { template: doc.template, ...target }),
    staff<Preview>('preview_source', {
      ...target,
      print_format: doc.printFormat || chosen?.print_format || null,
      letter_head: doc.letterHead || chosen?.letter_head || null,
    }),
    staff<Prefill[]>('preview_prefill', { template: doc.template, ...target }),
  ])
  recipients.value = rows.map((row) => ({ ...row, full_name: row.full_name ?? '', email: row.email ?? '' }))
  preview.value = rendered
  prefill.value = values
  pdf.value = await fetchPdf(`/api/method/${STAFF_API}preview_pdf?key=${encodeURIComponent(rendered.key)}`)
}

async function changeTemplate() {
  busy.value = true
  try {
    await loadTemplate()
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  const query = route.query
  const text = (key: string) => (typeof query[key] === 'string' ? (query[key] as string) : '')
  doc.doctype = text('doctype')
  doc.name = text('name')
  doc.template = text('template')
  doc.printFormat = text('print_format')
  doc.letterHead = text('letter_head')
  if (doc.doctype && doc.name) void loadDocument()
})

async function uploadSource(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  busy.value = true
  try {
    const staged = await staff<{ file_url: string; metrics: PageMetric[] }>('upload_pdf', {
      file_name: file.name,
      content: await fileToBase64(file),
    })
    sourceFile.value = staged.file_url
    pdf.value = await file.arrayBuffer()
    store.load({
      title: file.name,
      page_metrics: staged.metrics,
      roles: [{ role_label: __('Signer 1'), kind: 'Signer', routing_order: 1 }],
    })
    recipients.value = [
      { role_label: __('Signer 1'), kind: 'Signer', routing_order: 1, full_name: '', email: '' },
    ]
    form.title = form.title || file.name.replace(/\.pdf$/i, '')
    mode.value = 'upload'
    step.value = 'recipients'
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

// For an uploaded PDF the roles are edited in RolesPanel; the recipient rows follow them.
watch(
  () => store.roles.map((role) => [role.role_label, role.kind, role.routing_order].join('|')),
  () => {
    if (mode.value !== 'upload') return
    recipients.value = store.roles.map((role) => {
      const existing = recipients.value.find((r) => r.role_label === role.role_label)
      return {
        full_name: '',
        email: '',
        ...existing,
        role_label: role.role_label,
        kind: role.kind,
        routing_order: role.routing_order,
      }
    })
  },
)

const recipientsValid = computed(
  () =>
    recipients.value.length > 0 &&
    recipients.value.every((r) => r.full_name.trim() && /.+@.+\..+/.test(r.email)),
)

async function send() {
  if (mode.value === 'document') return sendDocument()
  busy.value = true
  try {
    const payload: Record<string, unknown> = {
      title: form.title,
      message: form.message,
      recipients: recipients.value,
    }
    if (mode.value === 'template') payload.template_version = templateVersion.value
    else {
      Object.assign(payload, {
        source_file: sourceFile.value,
        signing_order: form.signingOrder,
        otp_mode: form.otpMode,
        fields: store.payload().fields,
      })
    }
    const { name } = await staff<{ name: string }>('create_envelope', { payload })
    try {
      await staff('send_envelope', { envelope: name })
      toast.success(__('Sending {0}', [name]))
    } catch (error) {
      // The draft exists; open it so the sender can fix the problem and send from there.
      toast.error(errorMessage(error))
    }
    await router.push(`/envelopes/${name}`)
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

async function sendDocument() {
  busy.value = true
  try {
    const { name } = await staff<{ name: string }>('send_from_document', {
      doctype: doc.doctype,
      name: doc.name,
      template: doc.template,
      recipients: recipients.value,
      message: form.message,
      print_format: doc.printFormat || null,
      letter_head: doc.letterHead || null,
    })
    toast.success(__('Sending {0}', [name]))
    await router.push(`/envelopes/${name}`)
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

function next() {
  const index = steps.value.indexOf(step.value)
  step.value = steps.value[index + 1] ?? step.value
}
</script>

<template>
  <AppPageHeader :title="__('New request')" />
  <div class="max-w-6xl p-4 sm:p-5" data-testid="send-wizard">
    <ol class="flex gap-2 text-sm">
      <li
        v-for="(name, index) in steps"
        :key="name"
        class="rounded px-2 py-1"
        :class="step === name ? 'bg-surface-gray-4 text-ink-gray-9' : 'text-ink-gray-5'"
      >
        {{ index + 1 }}.
        {{
          __(
            name === 'source'
              ? 'Document'
              : name === 'recipients'
                ? 'People'
                : name === 'fields'
                  ? 'Fields'
                  : name === 'preview'
                    ? 'Preview'
                    : 'Review',
          )
        }}
      </li>
    </ol>

    <section v-if="step === 'source'" class="mt-6 grid gap-6 md:grid-cols-3">
      <div class="rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <h2 class="mb-3 text-base font-semibold text-ink-gray-8">{{ __('From a template') }}</h2>
        <button
          v-for="template in templates.data ?? []"
          :key="template.name"
          type="button"
          class="block w-full rounded px-3 py-2 text-start hover:bg-surface-gray-2"
          :disabled="busy"
          @click="
            chooseTemplate(
              template.name,
              template.published_version,
              template.title,
              template.source_type,
              template.reference_doctype,
            )
          "
        >
          {{ template.title }}
        </button>
        <p v-if="templates.data && !templates.data.length" class="text-sm text-ink-gray-5">
          {{ __('No published templates.') }}
        </p>
      </div>
      <div
        class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-base p-4"
        data-testid="document-source"
      >
        <h2 class="text-base font-semibold text-ink-gray-8">{{ __('From a document') }}</h2>
        <p class="text-sm text-ink-gray-5">{{ __('Rendered with its Print Format.') }}</p>
        <FormControl v-model="doc.doctype" :label="__('DocType')" placeholder="Quotation" />
        <FormControl v-model="doc.name" :label="__('Document')" />
        <Button
          :label="__('Load')"
          :loading="busy"
          :disabled="!doc.doctype || !doc.name"
          data-testid="load-document"
          @click="loadDocument"
        />
      </div>
      <label
        class="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-outline-gray-2 bg-surface-base p-8 text-center hover:bg-surface-gray-1"
      >
        <span class="text-base font-semibold text-ink-gray-8">{{ __('Upload a PDF') }}</span>
        <span class="mt-1 text-sm text-ink-gray-5">{{ __('Then place the fields yourself.') }}</span>
        <input
          type="file"
          accept="application/pdf"
          class="hidden"
          data-testid="source-upload"
          @change="uploadSource"
        />
      </label>
    </section>

    <section v-else-if="step === 'recipients'" class="mt-6 max-w-2xl space-y-4">
      <div v-if="mode === 'upload'" class="rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <RolesPanel />
      </div>
      <div v-if="mode === 'document'" class="rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <p class="mb-2 text-sm text-ink-gray-7">{{ __(doc.doctype) }} {{ doc.name }}</p>
        <FormControl
          v-model="doc.template"
          type="select"
          :label="__('Template')"
          :options="documentTemplates.map((t) => ({ label: t.title, value: t.name }))"
          @change="changeTemplate"
        />
      </div>
      <div class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <div v-for="row in recipients" :key="row.role_label" class="grid gap-2 sm:grid-cols-[8rem_1fr_1fr]">
          <span class="self-center text-sm font-medium text-ink-gray-7"
            >{{ row.role_label }} <span class="text-ink-gray-5">({{ roleKindLabel(row.kind) }})</span></span
          >
          <FormControl v-model="row.full_name" :placeholder="__('Full name')" />
          <FormControl v-model="row.email" type="email" :placeholder="__('Email')" />
          <p
            v-if="mode === 'document' && row.resolved === false"
            class="text-xs text-ink-gray-5 sm:col-start-2"
          >
            {{ __('Not found on the document. Enter it here.') }}
          </p>
        </div>
      </div>
      <Button variant="solid" :label="__('Next')" @click="next" />
    </section>

    <section v-else-if="step === 'fields'" class="mt-6 grid gap-4 md:grid-cols-[12rem_1fr]">
      <aside class="space-y-1">
        <p class="mb-2 text-xs text-ink-gray-5">
          {{ __('For {0}. Pick a type, then click the page.', [store.activeRole]) }}
        </p>
        <select v-model="store.activeRole" class="form-select mb-2 w-full">
          <option v-for="role in store.signerRoles" :key="role.role_label" :value="role.role_label">
            {{ role.role_label }}
          </option>
        </select>
        <button
          v-for="type in FIELD_TYPES"
          :key="type"
          type="button"
          class="block w-full rounded px-2 py-1.5 text-start text-sm"
          :class="placing === type ? 'bg-surface-gray-4 font-medium' : 'hover:bg-surface-gray-2'"
          @click="placing = placing === type ? null : type"
        >
          {{ __(type) }}
        </button>
        <Button
          class="mt-4 w-full"
          variant="solid"
          :label="__('Next')"
          :disabled="!store.fields.length"
          @click="next"
        />
      </aside>
      <div class="rounded-lg bg-surface-gray-2 p-3">
        <DesignerCanvas :source="pdf" :placing="placing" @placed="placing = null" />
      </div>
    </section>

    <section v-else-if="step === 'preview'" class="mt-6 grid gap-4 lg:grid-cols-[1fr_18rem]">
      <div class="rounded-lg bg-surface-gray-2 p-3" data-testid="anchor-preview">
        <AnchorPreview
          :source="pdf"
          :pages="preview?.metrics ?? []"
          :anchors="preview?.anchors ?? []"
          :roles="signerTokens"
        />
      </div>
      <aside class="space-y-4">
        <p
          v-if="preview && !preview.generator_tested"
          class="rounded bg-surface-amber-2 p-2 text-sm text-ink-amber-3"
        >
          {{
            __(
              'This Print Format uses the {0} generator. Fields from sign_field() are tested only with wkhtmltopdf and chrome; check their places.',
              [preview.generator],
            )
          }}
        </p>
        <div>
          <h2 class="mb-2 text-sm font-semibold text-ink-gray-8">{{ __('Fields from the Print Format') }}</h2>
          <ul class="space-y-1 text-sm text-ink-gray-7">
            <li v-for="anchor in preview?.anchors ?? []" :key="anchor.tag">
              {{ anchor.role }} · {{ __(anchor.field_type) }} · {{ __('page {0}', [anchor.page]) }}
              <span v-if="!signerTokens.includes(anchor.role)" class="block text-xs text-ink-red-4">
                {{ __('No signer has this role; the field stays empty.') }}
              </span>
            </li>
          </ul>
          <p v-if="preview && !preview.anchors.length" class="text-sm text-ink-gray-5">
            {{ __("No sign_field() found. The template's own fields are used.") }}
          </p>
        </div>
        <div v-if="prefill.length">
          <h2 class="mb-2 text-sm font-semibold text-ink-gray-8">{{ __('Filled from the document') }}</h2>
          <dl class="space-y-1 text-sm">
            <div v-for="row in prefill" :key="row.field_key" class="flex justify-between gap-2">
              <dt class="text-ink-gray-5">{{ row.field_key }}</dt>
              <dd class="text-ink-gray-8">{{ row.value }}</dd>
            </div>
          </dl>
        </div>
        <Button variant="solid" :label="__('Next')" data-testid="preview-next" @click="next" />
      </aside>
    </section>

    <section
      v-else
      class="mt-6 max-w-2xl space-y-3 rounded-lg border border-outline-gray-1 bg-surface-base p-4"
    >
      <FormControl v-model="form.title" :label="__('Title')" />
      <FormControl v-model="form.message" type="textarea" :label="__('Message (optional)')" />
      <template v-if="mode === 'upload'">
        <FormControl
          v-model="form.signingOrder"
          type="select"
          :label="__('Signing order')"
          :options="['Sequential', 'Parallel'].map((value) => ({ label: signingOrderLabel(value), value }))"
        />
        <FormControl
          v-model="form.otpMode"
          type="select"
          :label="__('Verify with an emailed code')"
          :options="['Off', 'Email'].map((value) => ({ label: otpModeLabel(value), value }))"
        />
      </template>
      <ul class="text-sm text-ink-gray-7">
        <li v-for="row in recipients" :key="row.role_label">
          {{ row.role_label }}: {{ row.full_name }} &lt;{{ row.email }}&gt;
        </li>
      </ul>
      <p v-if="!recipientsValid" class="text-sm text-ink-red-4">
        {{ __('Every person needs a name and an email address.') }}
      </p>
      <Button
        variant="solid"
        :loading="busy"
        :disabled="!recipientsValid || !form.title"
        :label="__('Send')"
        data-testid="send"
        @click="send"
      />
    </section>
  </div>
</template>
