app_name = "frappe_sign"
app_title = "Frappe Sign"
app_publisher = "Upscape Technologies"
app_description = "E-signatures for Frappe and ERPNext v16"
app_email = "info@upscapetech.com"
app_license = "mit"

# ERPNext is optional (D4). ERPNext code lives in frappe_sign/erpnext/ and is loaded only when
# "erpnext" is in frappe.get_installed_apps().
required_apps = ["frappe"]
