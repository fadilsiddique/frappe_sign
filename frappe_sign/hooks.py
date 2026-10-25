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

# sign_field() places signature fields in Print Formats (DESIGN 4.2).
jinja = {"methods": ["frappe_sign.jinja.sign_field"]}

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

# Sign Users see envelopes they sent, receive or were shared (DESIGN 1).
permission_query_conditions = {
	"Sign Envelope": "frappe_sign.utils.permissions.envelope_query_conditions",
}
has_permission = {
	"Sign Envelope": "frappe_sign.utils.permissions.envelope_has_permission",
}

after_request = ["frappe_sign.utils.http.after_request"]

# ERPNext (D4): company fields become Link Company when ERPNext is installed (DESIGN 2.1). Each hook
# returns at once on a site without ERPNext.
after_install = "frappe_sign.erpnext.setup.after_install"
after_app_install = ["frappe_sign.erpnext.setup.after_app_install"]
before_app_uninstall = ["frappe_sign.erpnext.setup.before_app_uninstall"]
after_migrate = ["frappe_sign.erpnext.setup.after_migrate"]

# Sign Settings adds custom fields to the DocTypes it enables (DESIGN 2.5).
doc_events = {
	"Sign Settings": {"on_update": "frappe_sign.services.doctypes.on_settings_update"},
}

# ERPNext sites get a test Company before frappe_sign's tests (tests/erpnext/).
before_tests = "frappe_sign.tests.erpnext.bootstrap.before_tests"
