<script setup lang="ts">
// Read-only preview of a rendered Print Format with the fields its sign_field() anchors place
// (DESIGN 4.2). Boxes use the normalized rects from the server, coloured by role.
import PdfViewer from '@/shared/components/PdfViewer.vue'
import type { PageMetric } from '@/shared/coords'
import { __ } from '@/shared/translate'
import { ROLE_COLORS } from '../designer/store'

export interface PreviewAnchor {
  tag: string
  role: string
  field_type: string
  n: number
  page: number
  x: number
  y: number
  w: number
  h: number
}

const props = defineProps<{
  source: ArrayBuffer | null
  pages: PageMetric[]
  anchors: PreviewAnchor[]
  roles: string[]
}>()

function color(role: string): string {
  const index = props.roles.indexOf(role)
  return index < 0 ? '#9ca3af' : ROLE_COLORS[index % ROLE_COLORS.length]
}
</script>

<template>
  <PdfViewer :source="source" :pages="pages" :max-width="760">
    <template #page="{ page }">
      <div
        v-for="anchor in anchors.filter((a) => a.page === page)"
        :key="anchor.tag"
        class="absolute rounded-sm border-2 border-dashed"
        :style="{
          left: `${anchor.x * 100}%`,
          top: `${anchor.y * 100}%`,
          width: `${anchor.w * 100}%`,
          height: `${anchor.h * 100}%`,
          borderColor: color(anchor.role),
          backgroundColor: `${color(anchor.role)}1a`,
        }"
        :title="anchor.tag"
        data-testid="anchor"
      >
        <span
          class="absolute start-0 top-0 whitespace-nowrap rounded-br px-1 text-[10px] leading-4 text-white"
          :style="{ backgroundColor: color(anchor.role) }"
          >{{ anchor.role }} · {{ __(anchor.field_type) }}</span
        >
      </div>
    </template>
  </PdfViewer>
</template>
