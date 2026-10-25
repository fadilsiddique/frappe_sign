<script setup lang="ts">
// Send wizard (P1.17): source (published template or an uploaded PDF), recipients, fields (for an
// uploaded PDF, placed with the designer canvas), review and send.
import { Button, call, createListResource, FormControl, toast } from 'frappe-ui'
import { computed, reactive, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { PageMetric } from '@/shared/coords'
import { __ } from '@/shared/translate'
import { errorMessage, fileToBase64, staff } from '../api'
import DesignerCanvas from '../designer/DesignerCanvas.vue'
import RolesPanel from '../designer/RolesPanel.vue'
import { FIELD_TYPES, useDesigner, type FieldType } from '../designer/store'

type Step = 'source' | 'recipients' | 'fields' | 'review'
interface Recipient {
  role_label: string
  kind: string
  routing_order: number
  full_name: string
  email: string
}

const router = useRouter()
const store = useDesigner()
const step = ref<Step>('source')
const mode = ref<'template' | 'upload'>('template')
const templateVersion = ref('')
const sourceFile = ref('')
const pdf = shallowRef<ArrayBuffer | null>(null)
const placing = ref<FieldType | null>(null)
const busy = ref(false)
const form = reactive({ title: '', message: '', signingOrder: 'Sequential', otpMode: 'Off' })
const recipients = ref<Recipient[]>([])

const templates = createListResource({
  doctype: 'Sign Template',
  fields: ['name', 'title', 'published_version'],
  filters: { published_version: ['is', 'set'], is_active: 1 },
  orderBy: 'title asc',
  pageLength: 200,
  auto: true,
})

const steps = computed<Step[]>(() =>
  mode.value === 'upload' ? ['source', 'recipients', 'fields', 'review'] : ['source', 'recipients', 'review'],
)

async function chooseTemplate(name: string, version: string, title: string) {
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

function next() {
  const index = steps.value.indexOf(step.value)
  step.value = steps.value[index + 1] ?? step.value
}
</script>

<template>
  <div class="mx-auto max-w-6xl p-6" data-testid="send-wizard">
    <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Send a document') }}</h1>
    <ol class="mt-3 flex gap-2 text-sm">
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
                ? 'Recipients'
                : name === 'fields'
                  ? 'Fields'
                  : 'Review',
          )
        }}
      </li>
    </ol>

    <section v-if="step === 'source'" class="mt-6 grid gap-6 md:grid-cols-2">
      <div class="rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <h2 class="mb-3 text-base font-semibold text-ink-gray-8">{{ __('From a template') }}</h2>
        <button
          v-for="template in templates.data ?? []"
          :key="template.name"
          type="button"
          class="block w-full rounded px-3 py-2 text-start hover:bg-surface-gray-2"
          :disabled="busy"
          @click="chooseTemplate(template.name, template.published_version, template.title)"
        >
          {{ template.title }}
        </button>
        <p v-if="templates.data && !templates.data.length" class="text-sm text-ink-gray-5">
          {{ __('No published templates.') }}
        </p>
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
      <div class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-base p-4">
        <div v-for="row in recipients" :key="row.role_label" class="grid gap-2 sm:grid-cols-[8rem_1fr_1fr]">
          <span class="self-center text-sm font-medium text-ink-gray-7"
            >{{ row.role_label }} <span class="text-ink-gray-5">({{ __(row.kind) }})</span></span
          >
          <FormControl v-model="row.full_name" :placeholder="__('Full name')" />
          <FormControl v-model="row.email" type="email" :placeholder="__('Email')" />
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

    <section
      v-else
      class="mt-6 max-w-2xl space-y-3 rounded-lg border border-outline-gray-1 bg-surface-base p-4"
    >
      <FormControl v-model="form.title" :label="__('Title')" />
      <FormControl v-model="form.message" type="textarea" :label="__('Message to signers')" />
      <template v-if="mode === 'upload'">
        <FormControl
          v-model="form.signingOrder"
          type="select"
          :label="__('Signing order')"
          :options="[
            { label: __('Sequential'), value: 'Sequential' },
            { label: __('Parallel'), value: 'Parallel' },
          ]"
        />
        <FormControl
          v-model="form.otpMode"
          type="select"
          :label="__('Verification')"
          :options="[
            { label: __('Off'), value: 'Off' },
            { label: __('Email code'), value: 'Email' },
          ]"
        />
      </template>
      <ul class="text-sm text-ink-gray-7">
        <li v-for="row in recipients" :key="row.role_label">
          {{ row.role_label }}: {{ row.full_name }} &lt;{{ row.email }}&gt;
        </li>
      </ul>
      <p v-if="!recipientsValid" class="text-sm text-ink-red-4">
        {{ __('Every recipient needs a name and an email address.') }}
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
