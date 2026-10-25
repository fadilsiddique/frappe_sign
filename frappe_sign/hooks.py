app_name = "frappe_sign"
app_title = "Frappe Sign"
app_publisher = "Upscape Technologies"
app_description = "E-signatures for Frappe and ERPNext v16"
app_email = "info@upscapetech.com"
app_license = "mit"

# ERPNext is optional (D4). ERPNext code lives in frappe_sign/erpnext/ and is loaded only when
# "erpnext" is in frappe.get_installed_apps().
required_apps = ["frappe"]

fixtures = [
	{"dt": "Role", "filters": [["role_name", "in", ["Sign Manager", "Sign User"]]]},
	# Email texts used by services/notify.py; it falls back to the same text if one is deleted.
	{"dt": "Email Template", "filters": [["name", "like", "Frappe Sign %"]]},
]

# SPA shells: www/sign.html (staff) and www/s.html (guest signing), built from frontend/.
website_route_rules = [
	{"from_route": "/sign/<path:app_path>", "to_route": "sign"},
	{"from_route": "/s/<path:app_path>", "to_route": "s"},
]

# Domain events (D17, DESIGN 8.5). Each handler runs in its own job as the envelope sender.
frappe_sign_events = {
	"envelope_sent": ["frappe_sign.services.notify.on_sent"],
	"recipient_signed": ["frappe_sign.services.notify.on_signed"],
	"envelope_completed": ["frappe_sign.services.notify.on_completed"],
	"envelope_declined": ["frappe_sign.services.notify.on_declined"],
	"envelope_voided": ["frappe_sign.services.notify.on_voided"],
}

scheduler_events = {
	"cron": {
		# Failed seals retry after 1, 5 and 30 minutes (DESIGN 5.4).
		"* * * * *": ["frappe_sign.jobs.seal.retry_due"],
	},
}
