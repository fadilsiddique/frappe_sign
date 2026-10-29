// Copyright (c) 2026, Upscape Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sign Certificate", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.storage === "Remote") {
			frm.add_custom_button(__("Read the certificate"), async () => {
				const response = await frappe.call({
					method: "frappe_sign.api.staff.check_remote_certificate",
					args: { certificate: frm.doc.name },
					type: "POST",
					freeze: true,
				});
				frappe.show_alert({
					message: __("Certificate read: {0}", [response.message.subject]),
					indicator: "green",
				});
				frm.reload_doc();
			});
		}
		if (!frm.is_new()) return;
		frm.set_intro(
			__(
				"Upload the .p12 file of your sealing certificate and enter its password. No certificate yet? Click Create test certificate."
			)
		);
		frm.add_custom_button(__("Create test certificate"), () =>
			window.frappe_sign.desk.test_certificate_dialog()
		);
	},
});
