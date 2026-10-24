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
]

# SPA shells: www/sign.html (staff) and www/s.html (guest signing), built from frontend/.
website_route_rules = [
	{"from_route": "/sign/<path:app_path>", "to_route": "sign"},
	{"from_route": "/s/<path:app_path>", "to_route": "s"},
]
