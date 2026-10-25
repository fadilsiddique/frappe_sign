// Frappe Sign in Desk (DESIGN 4.1): "Send for Signature" on the form, print view and list view of
// the DocTypes enabled in Sign Settings. Plain Frappe JS with frappe.ui.Dialog; the Vue staff app
// at /sign is only opened by "Customize".
frappe.provide("frappe_sign.desk");
frappe.provide("frappe.ui.form");

(() => {
	const desk = window.frappe_sign.desk;
	const API = "frappe_sign.api.staff";
	const STATUS_COLORS = {
		Sent: "blue",
		"Partially Signed": "orange",
		Signed: "green",
		Declined: "red",
		Voided: "gray",
		Expired: "gray",
	};

	const boot = () => frappe.boot.frappe_sign || { enabled_doctypes: [], can_send: false };
	const is_enabled = (doctype) => boot().can_send && boot().enabled_doctypes.includes(doctype);

	// Form: button and status indicator.
	$(document).on("form-refresh", (event, frm) => {
		if (!frm || !frm.doc || frm.is_new() || !is_enabled(frm.doctype)) return;
		const status = frm.doc.sign_status;
		if (status && status !== "Not Sent") {
			frm.dashboard.add_indicator(
				__("Signature: {0}", [__(status)]),
				STATUS_COLORS[status] || "gray"
			);
		}
		if (frm.doc.sign_envelope) {
			frm.add_custom_button(
				__("Signature Envelope"),
				() => window.open(`/sign/envelopes/${encodeURIComponent(frm.doc.sign_envelope)}`),
				__("Signature")
			);
		}
		if (frm.doc.docstatus < 2) {
			frm.add_custom_button(__("Send for Signature"), () =>
				desk.send_dialog({ doctype: frm.doctype, name: frm.docname, frm })
			);
		}
	});

	// Send dialog: template, recipients found on the document, message.
	desk.send_dialog = async ({ doctype, name, frm, print_format, letter_head }) => {
		const templates = await call("document_templates", { doctype });
		if (!templates.length) {
			frappe.msgprint({
				title: __("No template"),
				message: __(
					"Publish a Frappe Sign template for {0} first. Templates are made in {1}.",
					[__(doctype), `<a href="/sign/templates">/sign/templates</a>`]
				),
				indicator: "orange",
			});
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Send for Signature"),
			size: "large",
			fields: [
				{
					fieldname: "template",
					label: __("Template"),
					fieldtype: "Select",
					reqd: 1,
					options: templates.map((t) => ({ label: t.title, value: t.name })),
					default: templates[0].name,
					change: () => load_recipients(dialog, doctype, name),
				},
				print_format
					? {
							fieldname: "print_note",
							fieldtype: "HTML",
							options: `<p class="text-muted small">${__(
								"Print Format"
							)}: ${frappe.utils.escape_html(print_format)}${
								letter_head ? ", " + frappe.utils.escape_html(letter_head) : ""
							}</p>`,
					  }
					: { fieldtype: "HTML", fieldname: "print_note", options: "" },
				{
					fieldname: "recipients",
					label: __("Recipients"),
					fieldtype: "Table",
					cannot_add_rows: true,
					cannot_delete_rows: true,
					in_place_edit: true,
					data: [],
					fields: [
						{
							fieldname: "role_label",
							label: __("Role"),
							fieldtype: "Data",
							read_only: 1,
							in_list_view: 1,
							columns: 2,
						},
						{
							fieldname: "kind",
							label: __("Kind"),
							fieldtype: "Data",
							read_only: 1,
							in_list_view: 1,
							columns: 1,
						},
						{
							fieldname: "full_name",
							label: __("Name"),
							fieldtype: "Data",
							in_list_view: 1,
							reqd: 1,
							columns: 3,
						},
						{
							fieldname: "email",
							label: __("Email"),
							fieldtype: "Data",
							options: "Email",
							in_list_view: 1,
							reqd: 1,
							columns: 4,
						},
					],
				},
				{ fieldname: "message", label: __("Message to signers"), fieldtype: "Small Text" },
			],
			primary_action_label: __("Send"),
			primary_action: async (values) => {
				const recipients = dialog.fields_dict.recipients.df.data.map((row) => ({
					role_label: row.role_label,
					kind: row.kind,
					routing_order: row.routing_order,
					full_name: row.full_name,
					email: row.email,
					mobile: row.mobile,
					party_type: row.party_type,
					party: row.party,
					contact: row.contact,
				}));
				const missing = recipients.filter(
					(row) => row.kind !== "CC" && (!row.full_name || !row.email)
				);
				if (missing.length) {
					frappe.msgprint(
						__("Enter a name and email for {0}.", [
							missing.map((r) => r.role_label).join(", "),
						])
					);
					return;
				}
				dialog.disable_primary_action();
				try {
					const result = await call(
						"send_from_document",
						{
							doctype,
							name,
							template: values.template,
							recipients,
							message: values.message,
							print_format: print_format || null,
							letter_head: letter_head || null,
						},
						true
					);
					dialog.hide();
					frappe.show_alert({
						message: __("Sending {0} for signature", [result.name]),
						indicator: "green",
					});
					if (frm) setTimeout(() => frm.reload_doc(), 3000);
				} finally {
					dialog.enable_primary_action();
				}
			},
			secondary_action_label: __("Customize"),
			secondary_action: () => {
				const params = new URLSearchParams({
					doctype,
					name,
					template: dialog.get_value("template") || "",
				});
				if (print_format) params.set("print_format", print_format);
				if (letter_head) params.set("letter_head", letter_head);
				window.open(`/sign/new?${params.toString()}`);
			},
		});
		dialog.show();
		load_recipients(dialog, doctype, name);
	};

	async function load_recipients(dialog, doctype, name) {
		const template = dialog.get_value("template");
		if (!template) return;
		const rows = await call("resolve_recipients", { template, doctype, name });
		const table = dialog.fields_dict.recipients;
		table.df.data = rows.map((row) => ({
			...row,
			full_name: row.full_name || "",
			email: row.email || "",
		}));
		table.grid.refresh();
	}

	// Print view: send the print with the Print Format and Letter Head on screen. The print page
	// defines frappe.ui.form.PrintView when it first loads, so wrap the class when it is assigned.
	function patch_print_view(PrintView) {
		if (!PrintView || PrintView.__frappe_sign) return PrintView;
		const { setup_toolbar, show } = PrintView.prototype;
		PrintView.prototype.setup_toolbar = function () {
			setup_toolbar.call(this);
			this.frappe_sign_button = this.page.add_button(
				__("Send for Signature"),
				() => {
					const letterhead = this.get_letterhead();
					const format = this.selected_format();
					desk.send_dialog({
						doctype: this.frm.doctype,
						name: this.frm.docname,
						print_format: format && format !== "Standard" ? format : null,
						letter_head:
							letterhead && letterhead !== __("No Letterhead") ? letterhead : null,
					});
				},
				{ icon: "es-line-edit" }
			);
			this.frappe_sign_button.toggle(false);
		};
		PrintView.prototype.show = function (frm) {
			show.call(this, frm);
			this.frappe_sign_button?.toggle(is_enabled(frm.doctype) && frm.doc?.docstatus < 2);
		};
		PrintView.__frappe_sign = true;
		return PrintView;
	}

	let print_view_class = patch_print_view(frappe.ui.form.PrintView);
	Object.defineProperty(frappe.ui.form, "PrintView", {
		configurable: true,
		enumerable: true,
		get: () => print_view_class,
		set: (value) => {
			print_view_class = patch_print_view(value);
		},
	});

	// List view: bulk "Send for Signature", one envelope per selected document.
	const { get_actions_menu_items } = frappe.views.ListView.prototype;
	frappe.views.ListView.prototype.get_actions_menu_items = function () {
		const items = get_actions_menu_items.call(this);
		if (is_enabled(this.doctype)) {
			items.push({
				label: __("Send for Signature"),
				action: () => bulk_dialog(this),
				standard: false,
			});
		}
		return items;
	};

	async function bulk_dialog(list_view) {
		const names = list_view.get_checked_items(true);
		const templates = await call("document_templates", { doctype: list_view.doctype });
		if (!templates.length) {
			frappe.msgprint(
				__("Publish a Frappe Sign template for {0} first.", [__(list_view.doctype)])
			);
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Send {0} documents for signature", [names.length]),
			fields: [
				{
					fieldname: "template",
					label: __("Template"),
					fieldtype: "Select",
					reqd: 1,
					options: templates.map((t) => ({ label: t.title, value: t.name })),
					default: templates[0].name,
				},
				{
					fieldtype: "HTML",
					options: `<p class="text-muted small">${__(
						"Recipients come from each document. Documents without an email for a signer are skipped and listed in your notifications."
					)}</p>`,
				},
			],
			primary_action_label: __("Send"),
			primary_action: async ({ template }) => {
				const result = await call(
					"bulk_send",
					{ doctype: list_view.doctype, names, template },
					true
				);
				dialog.hide();
				list_view.clear_checked_items();
				frappe.show_alert({
					message: __("{0} documents queued for signature", [result.queued]),
					indicator: "green",
				});
			},
		});
		dialog.show();
	}

	async function call(method, args, post = false) {
		const response = await frappe.call({
			method: `${API}.${method}`,
			args,
			type: post ? "POST" : "GET",
			freeze: post,
		});
		return response.message;
	}
})();
