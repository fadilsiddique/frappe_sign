// Copyright (c) 2026, Upscape Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sign Template", {
	setup(frm) {
		frm.set_query("print_format", () => ({
			filters: { doc_type: frm.doc.reference_doctype },
		}));
	},

	refresh(frm) {
		show_staff_app_intro(frm);
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

// Print Format templates are easier to make in the staff app (UX_PLAN "Templates").
function show_staff_app_intro(frm) {
	const own_pdf = frm.doc.source_type === "Uploaded PDF";
	const path = frm.is_new()
		? "/sign/templates"
		: `/sign/templates/${encodeURIComponent(frm.doc.name)}/${own_pdf ? "design" : "edit"}`;
	const link = `<a href="${path}">${__("Open it in Frappe Sign")}</a>`;
	frm.set_intro(
		`<b>${__("Easier in Frappe Sign")}</b>: ${__(
			"pick the Print Format, name the people who sign and preview the page."
		)} ${link}`,
		"blue"
	);
}
