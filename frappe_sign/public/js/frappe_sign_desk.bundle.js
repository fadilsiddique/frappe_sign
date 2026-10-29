// Frappe Sign in Desk (DESIGN 4.1): "Send for Signature" on the form, print view and list view of
// the DocTypes enabled in Sign Settings. Plain Frappe JS with frappe.ui.Dialog; the Vue staff app
// at /sign is only opened by "Preview and edit".
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
		// The form message sits above the tabs; the dashboard is inside "Connections" in v16.
		if (status && status !== "Not Sent") {
			const envelope = frm.doc.sign_envelope
				? ` · <a href="/sign/requests/${encodeURIComponent(
						frm.doc.sign_envelope
				  )}">${frappe.utils.escape_html(frm.doc.sign_envelope)}</a>`
				: "";
			set_headline(frm, status, envelope);
		}
		if (frm.doc.sign_envelope) {
			frm.add_custom_button(
				__("Signature request"),
				() => window.open(`/sign/requests/${encodeURIComponent(frm.doc.sign_envelope)}`),
				__("Signature")
			);
		}
		if (frm.doc.docstatus < 2) {
			frm.add_custom_button(__("Send for Signature"), () =>
				desk.send_dialog({ doctype: frm.doctype, name: frm.docname, frm })
			);
		}
	});

	// "Signature: Sent", then who it waits for once the server says (an open request only).
	async function set_headline(frm, status, envelope) {
		let waiting = "";
		if (frm.doc.sign_envelope && ["Sent", "Partially Signed"].includes(status)) {
			try {
				const names = await call("waiting_on", { envelope: frm.doc.sign_envelope });
				if (names.length)
					waiting = ` · ${__("waiting for {0}", [
						frappe.utils.escape_html(names.join(", ")),
					])}`;
			} catch (error) {
				// The plain headline stays; a failed lookup must not break the form.
			}
		}
		frm.dashboard.clear_headline();
		frm.dashboard.set_headline_alert(
			`${__("Signature: {0}", [__(status)])}${waiting}${envelope}`,
			STATUS_COLORS[status] || "gray"
		);
	}

	// The recipients are plain rows: the grid's selection column does nothing here.
	$("<style>")
		.text(
			`.frappe-sign-send .grid-row-check, .frappe-sign-send .row-check,
			.frappe-sign-send .grid-footer, .frappe-sign-send .row-index { display: none !important; }
			.frappe-sign-send .grid-static-col, .frappe-sign-send .grid-static-col .static-area,
			.frappe-sign-send .grid-heading-row .grid-static-col { text-align: start; }`
		)
		.appendTo("head");

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
					label: __("Who signs"),
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
							columns: 3,
						},
						{
							fieldname: "kind",
							label: __("Kind"),
							fieldtype: "Data",
							read_only: 1,
							hidden: 1,
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
				{
					fieldname: "message_section",
					fieldtype: "Section Break",
					label: __("Add a message"),
					collapsible: 1,
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
			secondary_action_label: __("Preview and edit"),
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
		dialog.$wrapper.addClass("frappe-sign-send");
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
				watch_bulk_run(result.run);
			},
		});
		dialog.show();
	}

	// Progress of a bulk send: the job publishes after each document (jobs/bulk.py).
	function watch_bulk_run(run) {
		const title = __("Sending for signature");
		frappe.show_progress(title, 0, 100, __("Queued"), true);
		frappe.realtime.on("frappe_sign_bulk", function handler(progress) {
			if (progress.run !== run) return;
			if (progress.status !== "Done") {
				const message = __("{0} of {1} documents", [progress.done, progress.total]);
				frappe.show_progress(title, progress.done, progress.total, message, true);
				return;
			}
			frappe.realtime.off("frappe_sign_bulk", handler);
			frappe.hide_progress();
			const failed = progress.failed ? __(", {0} not sent", [progress.failed]) : "";
			frappe.msgprint({
				title,
				indicator: progress.failed ? "orange" : "green",
				message:
					__("{0} of {1} documents sent for signature", [
						progress.sent,
						progress.total,
					]) +
					failed +
					`. <a href="/app/sign-bulk-run/${encodeURIComponent(run)}">${__(
						"See each result"
					)}</a>`,
			});
		});
	}

	// Sign Certificate list and new form: "Create test certificate" (ADMIN_GUIDE step 2).
	desk.test_certificate_dialog = () => {
		const company_df = frappe.meta.get_docfield("Sign Certificate", "company") || {};
		const dialog = new frappe.ui.Dialog({
			title: __("Create test certificate"),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p class="text-muted small">${__(
						"Makes a self-signed certificate and uses it in the company's Sign Profile. It seals documents and shows any later change, but Adobe Reader shows its identity as unknown. For a green tick, upload a certificate from a trusted provider instead."
					)}</p>`,
				},
				{
					fieldname: "company",
					label: __("Company"),
					fieldtype: company_df.fieldtype === "Link" ? "Link" : "Data",
					options: company_df.fieldtype === "Link" ? company_df.options : undefined,
					default: frappe.defaults.get_user_default("Company"),
					onchange: () => {
						const company = dialog.get_value("company");
						if (company && !dialog.get_value("common_name")) {
							dialog.set_value("common_name", company);
						}
					},
				},
				{
					fieldname: "common_name",
					label: __("Name on the certificate"),
					fieldtype: "Data",
					reqd: 1,
					default: frappe.defaults.get_user_default("Company"),
					description: __("Adobe Reader shows this name in the signature panel."),
				},
				{
					fieldname: "years",
					label: __("Valid for (years)"),
					fieldtype: "Select",
					options: ["1", "2", "3", "5", "10"],
					default: "3",
				},
			],
			primary_action_label: __("Create"),
			primary_action: async ({ company, common_name, years }) => {
				const result = await call(
					"create_test_certificate",
					{ company, common_name, years: cint(years) },
					true
				);
				dialog.hide();
				frappe.msgprint({
					title: __("Certificate created"),
					indicator: "green",
					message: profile_message(result),
				});
				frappe.set_route("Form", "Sign Certificate", result.certificate);
			},
		});
		dialog.show();
	};

	function profile_message({ profile, profile_action }) {
		// get_form_link escapes the name and uses the version's Desk route (/app or /desk).
		const link = profile ? frappe.utils.get_form_link("Sign Profile", profile, true) : "";
		if (profile_action === "created") {
			return __("Sign Profile {0} was created with this certificate.", [link]);
		}
		if (profile_action === "linked") {
			return __("Sign Profile {0} now seals with this certificate.", [link]);
		}
		if (profile) {
			return __(
				"Sign Profile {0} already has a certificate and keeps it. To use the new one, select it on the profile.",
				[link]
			);
		}
		return __("Create a Sign Profile for your company and select this certificate on it.");
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
