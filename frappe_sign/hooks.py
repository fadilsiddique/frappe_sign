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

# Desk: Send for Signature on enabled DocTypes' forms, print view and list view (DESIGN 4.1).
app_include_js = "/assets/frappe_sign/js/desk.js"
boot_session = "frappe_sign.utils.boot.desk_boot"

# SPA shells: www/sign.html (staff) and www/s.html (guest signing), built from frontend/.
website_route_rules = [
	{"from_route": "/sign/<path:app_path>", "to_route": "sign"},
	{"from_route": "/s/<path:app_path>", "to_route": "s"},
]

# sign_field() places signature fields in Print Formats (DESIGN 4.2).
jinja = {"methods": ["frappe_sign.jinja.sign_field"]}

# Envelopes keep their own frozen PDF and audit trail, so they do not stop the source document's
# deletion; the dispatcher voids the open ones (DESIGN 4.7).
ignore_links_on_delete = ["Sign Envelope", "Sign Trigger Log"]

# Suggested recipients per DocType (DESIGN 4.3). "*" is the fallback for other DocTypes. The
# ERPNext resolvers only run for ERPNext DocTypes, which exist only when ERPNext is installed.
frappe_sign_resolvers = {
	"Contact": "frappe_sign.services.resolvers.contact",
	"User": "frappe_sign.services.resolvers.user",
	"Quotation": "frappe_sign.erpnext.resolvers.quotation",
	"Sales Order": "frappe_sign.erpnext.resolvers.sales_order",
	"Purchase Order": "frappe_sign.erpnext.resolvers.purchase_order",
	"Contract": "frappe_sign.erpnext.resolvers.contract",
	"Customer": "frappe_sign.erpnext.resolvers.customer",
	"Supplier": "frappe_sign.erpnext.resolvers.supplier",
	"Lead": "frappe_sign.erpnext.resolvers.lead",
	"Employee": "frappe_sign.erpnext.resolvers.employee",
	"Job Offer": "frappe_sign.erpnext.resolvers.job_offer",
	"Job Applicant": "frappe_sign.erpnext.resolvers.job_applicant",
	"*": "frappe_sign.erpnext.resolvers.employee_linked",
}

# Domain events (D17, DESIGN 8.5). Each handler runs in its own job as the envelope sender.
frappe_sign_events = {
	"envelope_sent": ["frappe_sign.services.notify.on_sent", "frappe_sign.services.writeback.on_sent"],
	"recipient_signed": [
		"frappe_sign.services.notify.on_signed",
		"frappe_sign.services.writeback.on_partial",
	],
	"envelope_completed": [
		"frappe_sign.services.notify.on_completed",
		"frappe_sign.services.writeback.on_complete",
		"frappe_sign.services.actions.queue_post_sign",
	],
	"envelope_declined": [
		"frappe_sign.services.notify.on_declined",
		"frappe_sign.services.writeback.on_declined",
	],
	"envelope_voided": ["frappe_sign.services.notify.on_voided", "frappe_sign.services.writeback.on_voided"],
	"envelope_expired": ["frappe_sign.services.writeback.on_expired"],
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

# One dispatcher for Sign Triggers and lifecycle sync on every DocType (D8); it returns after one
# cache lookup unless the DocType is in services/gate.py's set. Sign Settings adds custom fields to
# the DocTypes it enables (DESIGN 2.5); it and Sign Trigger refresh the gate.
DISPATCH = "frappe_sign.services.trigger.dispatch"
doc_events = {
	"*": {
		"after_insert": DISPATCH,
		"on_update": DISPATCH,
		"on_update_after_submit": DISPATCH,
		"on_submit": DISPATCH,
		"on_cancel": DISPATCH,
		"on_trash": DISPATCH,
	},
	"Sign Settings": {
		"on_update": [
			"frappe_sign.services.doctypes.on_settings_update",
			"frappe_sign.services.gate.clear",
		],
	},
	"Sign Trigger": {
		"on_update": "frappe_sign.services.gate.clear",
		"on_trash": "frappe_sign.services.gate.clear",
	},
}

# ERPNext sites get a test Company before frappe_sign's tests (tests/erpnext/).
before_tests = "frappe_sign.tests.erpnext.bootstrap.before_tests"
