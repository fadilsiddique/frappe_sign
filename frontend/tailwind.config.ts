import type { Config } from 'tailwindcss'
import preset, { content } from 'frappe-ui/tailwind'

export default {
  presets: [preset],
  content: [...content, './staff.html', './guest.html', './src/**/*.{vue,js,ts}'],
} satisfies Config
