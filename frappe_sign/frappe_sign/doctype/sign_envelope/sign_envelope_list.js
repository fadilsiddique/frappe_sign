// Desk list for Sign Request: the same words and colors as the staff app's status badges.
frappe.listview_settings["Sign Envelope"] = {
	add_fields: ["status", "send_state", "sealing_state"],
	get_indicator(doc) {
		if (doc.send_state === "Failed") return [__("Send failed"), "red", "send_state,=,Failed"];
		if (doc.sealing_state === "Failed") return [__("Seal failed"), "red", "sealing_state,=,Failed"];
		const status = {
			Draft: [__("Draft"), "gray"],
			Sent: [__("Waiting"), "orange"],
			"In Progress": [__("Waiting"), "orange"],
			Completed: [__("Completed"), "green"],
			Declined: [__("Declined"), "red"],
			Voided: [__("Voided"), "gray"],
			Expired: [__("Expired"), "yellow"],
		}[doc.status];
		return status ? [status[0], status[1], `status,=,${doc.status}`] : [__(doc.status), "gray"];
	},
};
