// Copyright (c) 2026, Upscape Technologies and contributors
// For license information, please see license.txt

frappe.listview_settings["Sign Certificate"] = {
	onload(listview) {
		if (!frappe.model.can_create("Sign Certificate")) return;
		listview.page.add_inner_button(__("Create test certificate"), () =>
			window.frappe_sign.desk.test_certificate_dialog()
		);
	},
};
