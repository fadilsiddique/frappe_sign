"""before_tests hook: give an ERPNext site the Company and masters that tests/erpnext/ need.

ERPNext's own before_tests runs only when ERPNext's tests run, so a site that only runs frappe_sign
tests has no Company. This runs ERPNext's setup wizard once, with a test company, and commits like
ERPNext's hook does. Sites without ERPNext are left alone.
"""

import frappe
from frappe.utils import now_datetime

TEST_COMPANY = "Frappe Sign Test LLC"


def before_tests() -> None:
	if "erpnext" not in frappe.get_installed_apps() or frappe.db.a_row_exists("Company"):
		return
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	year = now_datetime().year
	frappe.clear_cache()
	setup_complete(
		{
			"currency": "AED",
			"full_name": "Test User",
			"company_name": TEST_COMPANY,
			"timezone": "Asia/Dubai",
			"company_abbr": "FST",
			"industry": "Services",
			"country": "United Arab Emirates",
			"fy_start_date": f"{year}-01-01",
			"fy_end_date": f"{year}-12-31",
			"language": "english",
			"company_tagline": "Testing",
			"email": "test@erpnext.com",
			"password": "test",
			"chart_of_accounts": "Standard",
		}
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (test bootstrap, as ERPNext's before_tests)
