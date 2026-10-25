<script setup lang="ts">
import { Badge, createListResource, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'
import AppPageHeader from '../components/AppPageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import HeaderAction from '../components/HeaderAction.vue'
import ResourceState from '../components/ResourceState.vue'

const router = useRouter()
const templates = createListResource({
  doctype: 'Sign Template',
  fields: ['name', 'title', 'published_version', 'source_type', 'modified'],
  orderBy: 'modified desc',
  pageLength: 50,
  auto: true,
})

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
</script>

<template>
  <AppPageHeader :title="__('Templates')">
    <template #primary>
      <HeaderAction icon="lucide-plus" :label="__('New template')" @click="create" />
    </template>
  </AppPageHeader>
  <div class="max-w-4xl p-4 sm:p-5" data-testid="templates">
    <div class="rounded-lg border border-outline-gray-1 bg-surface-base">
      <ResourceState :resource="templates">
        <template #empty>
          <EmptyState
            icon="lucide-file-text"
            :title="__('No templates yet')"
            :text="__('A template says who signs and where. Start one from your own PDF.')"
          />
        </template>
        <div class="divide-y divide-outline-gray-1">
          <RouterLink
            v-for="template in templates.data ?? []"
            :key="template.name"
            :to="`/templates/${template.name}/design`"
            class="flex items-center justify-between px-4 py-3 hover:bg-surface-gray-1"
          >
            <span class="text-base text-ink-gray-9">{{ template.title }}</span>
            <Badge
              :theme="template.published_version ? 'green' : 'gray'"
              :label="template.published_version ? __('Published') : __('Draft')"
            />
          </RouterLink>
        </div>
      </ResourceState>
    </div>
  </div>
</template>
