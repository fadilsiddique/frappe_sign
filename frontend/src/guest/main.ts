import App from './App.vue'
import { createGuestRouter } from './router'
import { mountApp } from '@/shared/app'
import '@/shared/style.css'

// The shared stylesheet takes the company brand color for buttons on this page.
document.documentElement.dataset.app = 'guest'

// Guest calls go through shared/api.ts (P1.12), which adds the X-Sign-Session header.
mountApp(App, createGuestRouter())
