// Copyright (c) 2026, Upscape Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sign Template", {
	setup(frm) {
		frm.set_query("print_format", () => ({
			filters: { doc_type: frm.doc.reference_doctype },
		}));
	},
});
