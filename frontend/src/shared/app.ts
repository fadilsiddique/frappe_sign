import { createApp, type Component, type Plugin } from 'vue'
import type { Router } from 'vue-router'
import { applyBoot, readBoot } from './boot'
import { __, setMessages } from './translate'

declare module 'vue' {
  interface ComponentCustomProperties {
    __: typeof __
  }
}

// Shared start-up for the staff and guest apps: boot data, translations, direction, router.
export function mountApp(root: Component, router: Router, plugins: Plugin[] = []): void {
  const boot = readBoot()
  setMessages(boot.messages)
  applyBoot(boot)

  const app = createApp(root)
  app.config.globalProperties.__ = __
  for (const plugin of plugins) app.use(plugin)
  app.use(router).mount('#app')
}
