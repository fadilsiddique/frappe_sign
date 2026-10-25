import { frappeRequest, setConfig } from 'frappe-ui'
import { createPinia } from 'pinia'
import App from './App.vue'
import { createStaffRouter } from './router'
import { mountApp } from '@/shared/app'
import '@/shared/style.css'

// Staff calls go through frappe-ui resources, which send the CSRF token from the boot data.
setConfig('resourceFetcher', frappeRequest)

// Pinia holds the designer state only (DESIGN 7.1).
mountApp(App, createStaffRouter(), [createPinia()])
