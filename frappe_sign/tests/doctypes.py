"""Enable DocTypes in Sign Settings for a test class, and take them off again.

Custom fields add columns, and MariaDB commits before DDL, so a test's rollback cannot undo them.
Enable in setUpClass, before any test data exists, and call disable_doctypes in tearDownClass:
it deletes the fields and their columns and commits.
"""

import frappe

from frappe_sign.services.doctypes import FIELDNAMES


def enable_doctypes(*doctypes: str) -> None:
	settings = frappe.get_single("Sign Settings")
	have = {row.reference_doctype for row in settings.enabled_doctypes}
	for doctype in doctypes:
		if doctype not in have:
			settings.append("enabled_doctypes", {"reference_doctype": doctype})
	settings.save()
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (tests own this setup)


def disable_doctypes(*doctypes: str) -> None:
	frappe.db.delete(
		"Sign Enabled DocType", {"parent": "Sign Settings", "reference_doctype": ["in", list(doctypes)]}
	)
	for doctype in doctypes:
		for name in frappe.get_all(
			"Custom Field", filters={"dt": doctype, "fieldname": ["in", FIELDNAMES]}, pluck="name"
		):
			frappe.delete_doc("Custom Field", name, force=True)
		columns = set(frappe.db.get_table_columns(doctype))
		for fieldname in FIELDNAMES:
			if fieldname in columns:
				frappe.db.sql_ddl(f"alter table `tab{doctype}` drop column `{fieldname}`")
		frappe.clear_cache(doctype=doctype)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (tests own this cleanup)
