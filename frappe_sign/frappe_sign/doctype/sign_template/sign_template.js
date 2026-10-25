// Copyright (c) 2026, Upscape Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sign Template", {
	setup(frm) {
		frm.set_query("print_format", () => ({
			filters: { doc_type: frm.doc.reference_doctype },
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		// Senders see only published versions; Print Format templates are published from here.
		frm.add_custom_button(__("Publish"), async () => {
			if (frm.is_dirty()) await frm.save();
			const { message } = await frappe.call({
				method: "frappe_sign.api.staff.publish_template",
				args: { template: frm.doc.name },
				freeze: true,
			});
			frappe.show_alert({
				message: __("Published version {0}", [message.version_no]),
				indicator: "green",
			});
			frm.reload_doc();
		});
		if (frm.doc.source_type === "Uploaded PDF") {
			frm.add_custom_button(__("Open designer"), () =>
				window.open(`/sign/templates/${encodeURIComponent(frm.doc.name)}/design`)
			);
		}
	},
});
