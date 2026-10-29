<script setup lang="ts">
// Send wizard (UX_PLAN "New request", P1.17, P2.9, U.6). Step 1 picks the document (an ERPNext
// document, a template or an uploaded PDF), step 2 the people, then the fields (uploaded PDF) or
// a check of the rendered document, then Send. Desk's "Customize" opens it with
// ?doctype=&name=&template=&print_format=&letter_head= and goes straight to the people.
import { Button, call, FormControl, toast } from 'frappe-ui'
import { computed, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { PageMetric } from '@/shared/coords'
import { __ } from '@/shared/translate'
import { errorMessage, fetchPdf, fileToBase64, STAFF_API, staff } from '../api'
import AnchorPreview from '../components/AnchorPreview.vue'
import AppPageHeader from '../components/AppPageHeader.vue'
import { otpModeLabel, signingOrderLabel } from '../labels'
import DesignerCanvas from '../designer/DesignerCanvas.vue'
import RolesPanel from '../designer/RolesPanel.vue'
import { FIELD_TYPES, useDesigner, type FieldType } from '../designer/store'
import PeopleStep from '../send/PeopleStep.vue'
import SourceStep from '../send/SourceStep.vue'
import StepBar from '../send/StepBar.vue'
import type { DocumentTemplate, Mode, Prefill, Preview, Recipient, SourcePick, Step } from '../send/types'
import { checkWarnings, roleToken } from '../send/warnings'

const route = useRoute()
const router = useRouter()
const store = useDesigner()
const step = ref<Step>('source')
const mode = ref<Mode>('template')
const pick = ref<SourcePick>({ choice: 'document', doctype: '', name: '', template: '' })
const order = ref<string | null>(null)
const showMessage = ref(false)
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

const steps = computed<Step[]>(() => {
  // Before the first step is done, the steps follow the choice being made.
  const kind = step.value === 'source' ? pick.value.choice : mode.value
  if (kind === 'upload') return ['source', 'recipients', 'fields', 'review']
  if (kind === 'document') return ['source', 'recipients', 'preview', 'review']
  return ['source', 'recipients', 'review']
})

// Anchor roles are role labels with spaces as underscores (pdf/anchors.py role_token).
const signerTokens = computed(() =>
  recipients.value.filter((r) => r.kind === 'Signer').map((r) => roleToken(r.role_label)),
)
const warnings = computed(() => checkWarnings(preview.value?.anchors ?? [], recipients.value))

async function chooseTemplate(name: string) {
  busy.value = true
  try {
    const values = await call<{ published_version: string; title: string }>('frappe.client.get_value', {
      doctype: 'Sign Template',
      filters: name,
      fieldname: ['published_version', 'title'],
    })
    const snapshot = await call<{ snapshot: string }>('frappe.client.get_value', {
      doctype: 'Sign Template Version',
      filters: values.published_version,
      fieldname: 'snapshot',
    })
    const parsed = JSON.parse(snapshot.snapshot) as {
      roles: Recipient[]
      signing_order: string
      otp_mode: string
    }
    templateVersion.value = values.published_version
    form.title = form.title || values.title
    order.value = parsed.signing_order
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
  if (doc.doctype && doc.name) {
    pick.value = { choice: 'document', doctype: doc.doctype, name: doc.name, template: doc.template }
    void loadDocument()
  }
})

async function uploadSource(file: File) {
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
    await router.push(`/requests/${name}`)
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
    await router.push(`/requests/${name}`)
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

const index = computed(() => steps.value.indexOf(step.value))
const isLast = computed(() => step.value === 'review')

const canNext = computed(() => {
  if (busy.value) return false
  if (step.value === 'source') {
    if (pick.value.choice === 'document') return Boolean(pick.value.doctype && pick.value.name)
    return pick.value.choice === 'template' && Boolean(pick.value.template)
  }
  if (step.value === 'recipients') return recipientsValid.value
  if (step.value === 'fields') return store.fields.length > 0
  return true
})

// The first step does the loading; the others only move on.
function next() {
  if (step.value === 'source') {
    if (pick.value.choice === 'document') {
      doc.doctype = pick.value.doctype
      doc.name = pick.value.name
      doc.template = pick.value.template
      doc.printFormat = ''
      doc.letterHead = ''
      form.title = ''
      return void loadDocument()
    }
    form.title = ''
    return void chooseTemplate(pick.value.template)
  }
  step.value = steps.value[index.value + 1] ?? step.value
}

function back() {
  step.value = steps.value[index.value - 1] ?? step.value
}
</script>

<template>
  <AppPageHeader :title="__('New request')" />
  <div class="flex min-h-[calc(100dvh-3rem)] flex-col" data-testid="send-wizard">
    <div class="flex flex-1 flex-col gap-6 p-4 sm:p-5">
      <StepBar :steps="steps" :current="step" @go="step = $event" />

      <SourceStep v-if="step === 'source'" v-model="pick" :busy="busy" @upload="uploadSource" />

      <section v-else-if="step === 'recipients'" class="flex flex-col gap-4">
        <div
          v-if="mode === 'upload'"
          class="max-w-3xl rounded-lg border border-outline-gray-1 bg-surface-base p-4"
        >
          <RolesPanel />
        </div>
        <div v-if="mode === 'document'" class="flex max-w-3xl flex-wrap items-end gap-3">
          <p class="min-w-48 flex-1 text-base text-ink-gray-9">{{ __(doc.doctype) }} {{ doc.name }}</p>
          <FormControl
            v-if="documentTemplates.length > 1"
            v-model="doc.template"
            class="w-64"
            type="select"
            :label="__('Template')"
            :options="documentTemplates.map((t) => ({ label: t.title, value: t.name }))"
            @change="changeTemplate"
          />
        </div>
        <PeopleStep
          v-if="mode !== 'upload'"
          :recipients="recipients"
          :order="order"
          :from-document="mode === 'document'"
        />
        <PeopleStep v-else :recipients="recipients" :order="form.signingOrder" :from-document="false" />
      </section>

      <section v-else-if="step === 'fields'" class="grid gap-4 md:grid-cols-[12rem_1fr]">
        <aside class="space-y-1">
          <p class="mb-2 text-sm text-ink-gray-6">
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
        </aside>
        <div class="rounded-lg bg-surface-gray-2 p-3">
          <DesignerCanvas :source="pdf" :placing="placing" @placed="placing = null" />
        </div>
      </section>

      <section v-else-if="step === 'preview'" class="grid gap-4 lg:grid-cols-[1fr_20rem] lg:items-start">
        <div class="rounded-lg bg-surface-gray-2 p-3" data-testid="anchor-preview">
          <AnchorPreview
            :source="pdf"
            :pages="preview?.metrics ?? []"
            :anchors="preview?.anchors ?? []"
            :roles="signerTokens"
          />
        </div>
        <aside class="flex flex-col gap-5">
          <div v-if="warnings.length" class="flex flex-col gap-2" data-testid="warnings">
            <h2 class="text-base font-semibold text-ink-gray-9">{{ __('Check before sending') }}</h2>
            <ul class="flex flex-col gap-1.5">
              <li
                v-for="warning in warnings"
                :key="warning"
                class="flex gap-2 rounded bg-surface-amber-2 p-2 text-sm text-ink-amber-3"
              >
                <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />{{ warning }}
              </li>
            </ul>
          </div>
          <p v-else class="flex items-center gap-2 text-sm text-ink-green-4">
            <span class="lucide-check size-4" aria-hidden="true" />{{
              __('Every person has a field to fill.')
            }}
          </p>
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
            <h2 class="mb-2 text-base font-semibold text-ink-gray-9">{{ __('Fields on the document') }}</h2>
            <ul class="space-y-1 text-sm text-ink-gray-7">
              <li v-for="anchor in preview?.anchors ?? []" :key="anchor.tag">
                {{ anchor.role }} · {{ __(anchor.field_type) }} · {{ __('page {0}', [anchor.page]) }}
              </li>
            </ul>
          </div>
          <div v-if="prefill.length">
            <h2 class="mb-2 text-base font-semibold text-ink-gray-9">{{ __('Filled from the document') }}</h2>
            <dl class="space-y-1 text-sm">
              <div v-for="row in prefill" :key="row.field_key" class="flex justify-between gap-2">
                <dt class="text-ink-gray-6">{{ row.field_key }}</dt>
                <dd class="text-ink-gray-9">{{ row.value }}</dd>
              </div>
            </dl>
          </div>
        </aside>
      </section>

      <section v-else class="flex max-w-2xl flex-col gap-4">
        <FormControl v-model="form.title" :label="__('Title')" />
        <div>
          <Button
            v-if="!showMessage"
            variant="ghost"
            icon-left="lucide-plus"
            :label="__('Add a message')"
            @click="showMessage = true"
          />
          <FormControl
            v-else
            v-model="form.message"
            type="textarea"
            :rows="3"
            :label="__('Message')"
            :placeholder="__('Shown in the email to each person')"
          />
        </div>
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
        <ul
          class="flex flex-col divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1 bg-surface-base"
        >
          <li v-for="row in recipients" :key="row.role_label" class="flex flex-col gap-0.5 px-4 py-3">
            <span class="text-base text-ink-gray-9">{{ row.full_name }}</span>
            <span class="text-sm text-ink-gray-6">{{ row.role_label }} · {{ row.email }}</span>
          </li>
        </ul>
        <p v-if="!recipientsValid" class="text-sm text-ink-red-4">
          {{ __('Every person needs a name and an email address.') }}
        </p>
      </section>
    </div>

    <footer
      v-if="!(step === 'source' && pick.choice === 'upload')"
      class="sticky bottom-0 z-10 flex items-center justify-between gap-2 border-t border-outline-gray-1 bg-surface-base px-4 py-3 sm:px-5"
      data-testid="wizard-footer"
    >
      <Button variant="outline" :label="__('Back')" :disabled="index === 0" @click="back" />
      <Button
        v-if="isLast"
        variant="solid"
        icon-left="lucide-send"
        :loading="busy"
        :disabled="!recipientsValid || !form.title"
        :label="__('Send')"
        data-testid="send"
        @click="send"
      />
      <Button
        v-else
        variant="solid"
        :loading="busy"
        :disabled="!canNext"
        :label="__('Next')"
        data-testid="next"
        @click="next"
      />
    </footer>
  </div>
</template>
