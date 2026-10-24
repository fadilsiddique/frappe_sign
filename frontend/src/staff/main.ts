import { frappeRequest, setConfig } from 'frappe-ui'
import App from './App.vue'
import { createStaffRouter } from './router'
import { mountApp } from '@/shared/app'
import '@/shared/style.css'

// Staff calls go through frappe-ui resources, which send the CSRF token from the boot data.
setConfig('resourceFetcher', frappeRequest)

mountApp(App, createStaffRouter())
