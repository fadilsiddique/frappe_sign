<script setup lang="ts">
// Templates as a grid of cards: page thumbnail, title, type, state and when it was last used.
import { Badge, createResource, toast } from 'frappe-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import { errorMessage, STAFF_API, staff } from '../api'
import AppPageHeader from '../components/AppPageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import HeaderAction from '../components/HeaderAction.vue'
import ResourceState from '../components/ResourceState.vue'
import TemplateThumb from '../send/TemplateThumb.vue'
import NewTemplateDialog from '../templates/NewTemplateDialog.vue'
import { editRoute, isPrintFormat, lastUsedLine, typeLine } from '../templates/lines'
import type { TemplateCardRow } from '../templates/types'

const router = useRouter()
const creating = ref(false)
const templates = createResource({ url: `${STAFF_API}list_templates`, auto: true })

async function create() {
  const title = window.prompt(__('Template title'))
  if (!title) return
  try {
    const result = await staff<{ name: string }>('save_template', {
      data: {
        title,
        source_type: 'Uploaded PDF',
        roles: [
          { role_label: __('Signer 1'), kind: 'Signer', routing_order: 1, signer_source: 'Ask at Send' },
        ],
      },
    })
    await router.push(`/templates/${result.name}/design`)
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

function pick(kind: 'print-format' | 'pdf') {
  creating.value = false
  if (kind === 'print-format') void router.push('/templates/new/print-format')
  else void create()
}
</script>

<template>
  <AppPageHeader :title="__('Templates')">
    <template #primary>
      <HeaderAction
        icon="lucide-plus"
        :label="__('New template')"
        data-testid="new-template"
        @click="creating = true"
      />
    </template>
  </AppPageHeader>
  <NewTemplateDialog v-model="creating" @pick="pick" />
  <div class="p-4 sm:p-5" data-testid="templates">
    <ResourceState :resource="templates">
      <template #empty>
        <EmptyState
          icon="lucide-layout-template"
          :title="__('No templates yet')"
          :text="__('A template says who signs and where. Start one for a Quotation, or from your own PDF.')"
        />
      </template>
      <ul class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <li v-for="row in (templates.data ?? []) as TemplateCardRow[]" :key="row.name">
          <RouterLink
            :to="editRoute(row)"
            class="flex h-full flex-col gap-3 rounded-lg bg-surface-base p-2 transition-colors hover:bg-surface-gray-1 focus-visible:outline-2 focus-visible:outline-outline-gray-4"
            :data-testid="`template-${row.name}`"
          >
            <TemplateThumb :pdf-url="isPrintFormat(row) ? null : row.pdf_file" />
            <span class="flex flex-col gap-1 px-1 pb-1">
              <span class="truncate text-base font-medium text-ink-gray-9">{{ row.title }}</span>
              <span class="truncate text-sm text-ink-gray-6">{{ typeLine(row) }}</span>
              <span class="flex items-center justify-between gap-2 pt-1">
                <Badge
                  :theme="row.published_version ? 'green' : 'gray'"
                  :label="row.published_version ? __('Published') : __('Draft')"
                />
                <span class="truncate text-sm text-ink-gray-6">{{ lastUsedLine(row) }}</span>
              </span>
            </span>
          </RouterLink>
        </li>
      </ul>
    </ResourceState>
  </div>
</template>
