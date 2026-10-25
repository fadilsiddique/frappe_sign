<script setup lang="ts">
import { Badge, Button, createListResource, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import { __ } from '@/shared/translate'
import { errorMessage, staff } from '../api'

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
        roles: [{ role_label: 'Signer 1', kind: 'Signer', routing_order: 1, signer_source: 'Ask at Send' }],
      },
    })
    await router.push(`/templates/${result.name}/design`)
  } catch (error) {
    toast.error(errorMessage(error))
  }
}
</script>

<template>
  <div class="mx-auto max-w-4xl p-6" data-testid="templates">
    <div class="mb-4 flex items-center justify-between">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Templates') }}</h1>
      <Button variant="solid" :label="__('New template')" @click="create" />
    </div>
    <div class="divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1 bg-surface-base">
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
      <p v-if="templates.data && !templates.data.length" class="p-6 text-center text-ink-gray-5">
        {{ __('No templates yet.') }}
      </p>
    </div>
  </div>
</template>
