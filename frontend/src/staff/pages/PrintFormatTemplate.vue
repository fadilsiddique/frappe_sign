<script setup lang="ts">
// Make or edit a template for an ERPNext document, in the staff app (UX_PLAN "Templates"): the
// document type, its Print Format, who signs, what happens after, a preview, and Publish.
import { Button, call, FormControl, toast } from 'frappe-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'
import AppPageHeader from '../components/AppPageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import HeaderAction from '../components/HeaderAction.vue'
import { otpModeOptions, signingOrderLabel } from '../labels'
import { readBoot } from '@/shared/boot'
import AfterSigningEditor from '../templates/AfterSigningEditor.vue'
import { afterFromStored, afterProblem, afterToStored, emptyAfter } from '../templates/afterSigning'
import PeopleEditor from '../templates/PeopleEditor.vue'
import TemplatePreview from '../templates/TemplatePreview.vue'
import type { PersonRow, PrintFormatChoice, SettableField } from '../templates/types'

const props = defineProps<{ id?: string }>()
const router = useRouter()

const loading = ref(Boolean(props.id))
const loadError = ref('')
const saving = ref(false)
const templateName = ref(props.id ?? '')
const published = ref<string | null>(null)
const title = ref('')
const doctype = ref('')
const printFormat = ref('')
const signingOrder = ref('Sequential')
const otpMode = ref('Off')
const people = ref<PersonRow[]>([
  {
    role_label: 'Customer',
    kind: 'Signer',
    signer_source: 'Party Contact',
    source_field: '',
    fixed_user: '',
  },
  { role_label: 'Company', kind: 'Signer', signer_source: 'Ask at Send', source_field: '', fixed_user: '' },
])
const after = ref(emptyAfter())

const doctypes = ref<string[]>([])
const formats = ref<PrintFormatChoice[]>([])
const fields = ref<SettableField[]>([])

const format = computed(() => formats.value.find((row) => row.name === printFormat.value))
const problem = computed(() => {
  if (!title.value.trim()) return __('Give the template a title.')
  if (!doctype.value) return __('Pick the type of document.')
  if (!printFormat.value) return __('Pick the Print Format.')
  if (people.value.some((person) => !person.role_label)) return __('Every person needs a role name.')
  return afterProblem(after.value)
})
const needsDoctypes = computed(() => !loading.value && !doctypes.value.length)

interface TemplateDoc {
  title: string
  reference_doctype: string
  print_format: string
  signing_order: string
  otp_mode: string
  post_sign_action: string
  post_sign_config: string | null
  published_version: string | null
  roles: Array<PersonRow & { routing_order: number }>
}

async function load() {
  const known = await staff<Array<{ doctype: string }>>('sendable_doctypes')
  doctypes.value = known.map((row) => row.doctype)
  if (!props.id) {
    doctype.value = doctypes.value.includes('Quotation') ? 'Quotation' : (doctypes.value[0] ?? '')
    return
  }
  const doc = await call<TemplateDoc>('frappe.client.get', { doctype: 'Sign Template', name: props.id })
  title.value = doc.title
  doctype.value = doc.reference_doctype
  printFormat.value = doc.print_format ?? ''
  signingOrder.value = doc.signing_order
  otpMode.value = doc.otp_mode
  published.value = doc.published_version
  people.value = [...doc.roles]
    .sort((a, b) => a.routing_order - b.routing_order)
    .map((role) => ({
      role_label: role.role_label,
      kind: role.kind,
      signer_source: role.signer_source,
      source_field: role.source_field ?? '',
      fixed_user: role.fixed_user ?? '',
    }))
  after.value = afterFromStored(doc.post_sign_action, doc.post_sign_config)
  if (doctype.value && !doctypes.value.includes(doctype.value)) doctypes.value.push(doctype.value)
}

async function loadChoices(selected: string) {
  if (!selected) return
  formats.value = await staff<PrintFormatChoice[]>('template_print_formats', { doctype: selected })
  fields.value = await staff<SettableField[]>('template_doctype_fields', { doctype: selected })
}

// Changing the type clears the Print Format, which belongs to the old type.
watch(doctype, (value, before) => {
  if (before) printFormat.value = ''
  void loadChoices(value).catch((error) => toast.error(errorMessage(error)))
})

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    loadError.value = errorMessage(error)
  } finally {
    loading.value = false
  }
})

function payload() {
  const stored = afterToStored(after.value)
  return {
    title: title.value.trim(),
    source_type: 'Print Format',
    reference_doctype: doctype.value,
    print_format: printFormat.value,
    signing_order: signingOrder.value,
    otp_mode: otpMode.value,
    post_sign_action: stored.action,
    post_sign_config: JSON.stringify(stored.config),
    roles: people.value.map((person, index) => ({ ...person, routing_order: index + 1 })),
  }
}

async function save(): Promise<boolean> {
  if (problem.value) {
    toast.error(problem.value)
    return false
  }
  saving.value = true
  try {
    const result = await staff<{ name: string }>('save_template', {
      template: templateName.value || undefined,
      data: payload(),
    })
    if (!templateName.value) {
      templateName.value = result.name
      await router.replace(`/templates/${result.name}/edit`)
    }
    return true
  } catch (error) {
    toast.error(errorMessage(error))
    return false
  } finally {
    saving.value = false
  }
}

async function saveOnly() {
  if (await save()) toast.success(__('Saved'))
}

async function publish() {
  if (!(await save())) return
  try {
    const version = await staff<{ name: string; version_no: number }>('publish_template', {
      template: templateName.value,
    })
    published.value = version.name
    toast.success(__('Published version {0}', [version.version_no]))
  } catch (error) {
    toast.error(errorMessage(error))
  }
}
</script>

<template>
  <AppPageHeader :title="title || __('New template')">
    <template #actions>
      <Button
        variant="ghost"
        icon-left="lucide-arrow-left"
        :label="__('Templates')"
        @click="router.push('/templates')"
      />
      <Button
        variant="subtle"
        :label="__('Save')"
        :loading="saving"
        data-testid="save-template"
        @click="saveOnly"
      />
    </template>
    <template #primary>
      <HeaderAction
        icon="lucide-send"
        :label="__('Publish')"
        data-testid="publish-template"
        @click="publish"
      />
    </template>
  </AppPageHeader>

  <div class="p-4 sm:p-5" data-testid="print-format-template">
    <p v-if="loadError" class="text-ink-red-4" role="alert">{{ loadError }}</p>
    <EmptyState
      v-else-if="needsDoctypes"
      icon="lucide-file-check"
      :title="__('No document type is turned on for signing')"
      :text="__('Turn on a type, such as Quotation, in Sign Settings. Then come back to make its template.')"
    />
    <div v-else class="grid items-start gap-5 xl:grid-cols-[minmax(0,32rem)_minmax(0,1fr)]">
      <div class="flex flex-col gap-5">
        <section class="flex flex-col gap-4 rounded-lg bg-surface-base p-4" aria-labelledby="t-doc">
          <h2 id="t-doc" class="text-lg font-semibold text-ink-gray-9">{{ __('Document') }}</h2>
          <FormControl
            v-model="title"
            :label="__('Title')"
            :placeholder="__('Quotation for signature')"
            data-testid="template-title"
          />
          <FormControl
            v-model="doctype"
            type="select"
            :label="__('Type of document')"
            :options="doctypes.map((value) => ({ label: __(value), value }))"
            data-testid="template-doctype"
          />
          <FormControl
            v-model="printFormat"
            type="select"
            :label="__('Print Format')"
            :options="formats.map((row) => ({ label: row.name, value: row.name }))"
            data-testid="template-print-format"
          />
          <p
            v-if="format?.has_sign_fields"
            class="flex items-center gap-1.5 text-sm text-ink-green-3"
            data-testid="format-ok"
          >
            <span class="lucide-check size-4" aria-hidden="true" />{{ __('Has signature fields') }}
          </p>
          <p
            v-else-if="format"
            class="flex items-start gap-1.5 text-sm text-ink-amber-3"
            data-testid="format-missing"
          >
            <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {{
              __(
                'No signature fields yet. Add sign_field() to this Print Format; the anchor guide in the Admin guide shows how.',
              )
            }}
          </p>
        </section>

        <section class="flex flex-col gap-4 rounded-lg bg-surface-base p-4" aria-labelledby="t-people">
          <h2 id="t-people" class="text-lg font-semibold text-ink-gray-9">
            {{ __('People, in signing order') }}
          </h2>
          <PeopleEditor v-model="people" />
          <div class="grid gap-3 sm:grid-cols-2">
            <FormControl
              v-model="signingOrder"
              type="select"
              :label="__('Signing order')"
              :options="
                ['Sequential', 'Parallel'].map((value) => ({ label: signingOrderLabel(value), value }))
              "
            />
            <FormControl
              v-model="otpMode"
              type="select"
              :label="__('Verify the signer with a code')"
              :options="otpModeOptions(readBoot().whatsapp)"
            />
          </div>
        </section>

        <section class="flex flex-col gap-4 rounded-lg bg-surface-base p-4" aria-labelledby="t-after">
          <h2 id="t-after" class="text-lg font-semibold text-ink-gray-9">{{ __('After signing') }}</h2>
          <AfterSigningEditor v-model="after" :doctype="doctype" :fields="fields" />
        </section>
      </div>

      <section class="flex flex-col gap-4 rounded-lg bg-surface-base p-4" aria-labelledby="t-preview">
        <div class="flex items-center justify-between gap-2">
          <h2 id="t-preview" class="text-lg font-semibold text-ink-gray-9">{{ __('Preview') }}</h2>
          <span class="text-sm text-ink-gray-6">{{
            published ? __('Published: {0}', [published]) : __('Not published')
          }}</span>
        </div>
        <TemplatePreview v-if="printFormat" :doctype="doctype" :print-format="printFormat" :people="people" />
        <p v-else class="text-sm text-ink-gray-6">{{ __('Pick a Print Format to preview it.') }}</p>
      </section>
    </div>
  </div>
</template>
