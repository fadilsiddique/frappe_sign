"""Email notifications, Notification Log and realtime updates (DESIGN 8.7). WhatsApp arrives in P3.1.

Emails use the Email Templates shipped as fixtures ("Frappe Sign ..."); a template a site deleted
falls back to the built-in text. Signer links carry the plain token, which exists only in memory and
in the outgoing email, so invitations are sent by the service that issues the token, never by an
event handler. Emails reference the source document when there is one, so they show in its timeline.
"""

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.utils import escape_html, get_url

from frappe_sign.utils.boot import profile_branding
from frappe_sign.utils.dates import format_local

INVITATION = "Frappe Sign Invitation"
REMINDER = "Frappe Sign Reminder"
OTP = "Frappe Sign OTP"
COMPLETED = "Frappe Sign Completed"
DECLINED = "Frappe Sign Declined"
VOIDED = "Frappe Sign Voided"
FAILED = "Frappe Sign Failed"
REALTIME_EVENT = "frappe_sign_envelope"
DEFAULT_BRAND = "#111827"
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def signing_link(token: str) -> str:
	return get_url(f"/s/{token}")


def send_invitation(envelope: Any, recipient: Any, token: str, *, reminder: bool = False) -> None:
	context = base_context(envelope) | {
		"recipient_name": escape_html(recipient.full_name or ""),
		"link": signing_link(token),
		"expires_on": format_local(envelope.expires_on),
	}
	template = REMINDER if reminder else (template_email(envelope) or INVITATION)
	send(envelope, [recipient.email], template, context)


def try_send_invitation(envelope: Any, recipient: Any, token: str, *, reminder: bool = False) -> bool:
	"""Send the invitation; on an email setup error, log it, tell the sender and return False.

	A guest's signature must not fail because the next signer's email could not be queued; the
	sender can resend once email works.
	"""
	try:
		send_invitation(envelope, recipient, token, reminder=reminder)
	except frappe.OutgoingEmailError:
		frappe.log_error(
			title="Frappe Sign: email", reference_doctype="Sign Envelope", reference_name=envelope.name
		)
		notify_sender(
			envelope,
			_("The invitation to {0} could not be emailed. Check the Email Account and resend.").format(
				recipient.email
			),
		)
		return False
	return True


def can_send_email(company: str | None) -> bool:
	return bool(EmailAccount.find_outgoing(match_by_email=sender_address(company)))


def send_otp(envelope: Any, recipient: Any, code: str, minutes: int) -> None:
	context = base_context(envelope) | {
		"recipient_name": escape_html(recipient.full_name or ""),
		"otp": code,
		"minutes": minutes,
	}
	send(envelope, [recipient.email], OTP, context, now=True)


def send_failed(envelope: str, reason: str) -> None:
	"""Tell the sender that sending (render) or sealing failed."""
	doc = frappe.get_doc("Sign Envelope", envelope)
	context = base_context(doc) | {"reason": escape_html(reason)}
	send(doc, [sender_email(doc)], FAILED, context)
	notify_sender(doc, _("Frappe Sign could not finish {0}: {1}").format(doc.name, reason))


def on_sent(envelope: str) -> None:
	publish_realtime(envelope)


def on_signed(envelope: str) -> None:
	doc = frappe.get_doc("Sign Envelope", envelope)
	signed = [row.full_name for row in doc.recipients if row.status == "Signed"]
	notify_sender(doc, _("{0} signed {1}").format(signed[-1] if signed else _("A recipient"), doc.title))
	publish_realtime(envelope)


def on_completed(envelope: str) -> None:
	doc = frappe.get_doc("Sign Envelope", envelope)
	recipients = sorted(
		{row.email for row in doc.recipients if row.email and row.status != "Delegated"} | {sender_email(doc)}
	)
	attachments = [{"fid": doc.signed_file}] if doc.signed_file else None
	send(doc, recipients, COMPLETED, base_context(doc), attachments=attachments)
	notify_sender(doc, _("{0} is complete and sealed").format(doc.title))
	publish_realtime(envelope)


def on_declined(envelope: str) -> None:
	doc = frappe.get_doc("Sign Envelope", envelope)
	declined = next((row for row in doc.recipients if row.status == "Declined"), None)
	context = base_context(doc) | {
		"declined_by": escape_html(declined.full_name if declined else ""),
		"reason": escape_html(declined.decline_reason if declined else ""),
	}
	send(doc, [sender_email(doc)], DECLINED, context)
	notify_sender(doc, _("{0} was declined").format(doc.title))
	publish_realtime(envelope)


def on_voided(envelope: str) -> None:
	doc = frappe.get_doc("Sign Envelope", envelope)
	invited = [
		row.email for row in doc.recipients if row.email and row.status in ("Sent", "Viewed", "Signed")
	]
	if invited:
		context = base_context(doc) | {"reason": escape_html(doc.void_reason or "")}
		send(doc, invited, VOIDED, context)
	publish_realtime(envelope)


def sender_email(envelope: Any) -> str:
	return frappe.db.get_value("User", envelope.sender, "email") or envelope.sender


def base_context(envelope: Any) -> dict[str, Any]:
	brand = brand_color(envelope)
	return {
		"brand_color": brand,
		"button_text_color": contrast_color(brand),
		"envelope": envelope.name,
		"envelope_title": escape_html(envelope.title or ""),
		"message": escape_html(envelope.message or ""),
		"sender_name": escape_html(frappe.utils.get_fullname(envelope.sender) if envelope.sender else ""),
		"company": escape_html(envelope.company or ""),
	}


def brand_color(envelope: Any) -> str:
	"""The Sign Profile color for buttons, or a neutral dark gray when none is set."""
	color = profile_branding(envelope.company).get("brand_color") or ""
	return color if HEX_COLOR.match(color) else DEFAULT_BRAND


def contrast_color(background: str) -> str:
	"""Black or white text, whichever reads better on `background` (#RRGGBB)."""
	red, green, blue = (int(background[i : i + 2], 16) for i in (1, 3, 5))
	return "#111827" if (red * 299 + green * 587 + blue * 114) / 1000 > 150 else "#ffffff"


def wrap(message: str, envelope: Any) -> str:
	"""Put `message` in the branded shell: logo and company name on top, the body, then a footer.

	Table based HTML with inline styles, so Gmail and Outlook render it the same way.
	"""
	branding = profile_branding(envelope.company)
	name = escape_html(branding["company"] or envelope.company or "")
	logo = branding["logo"]
	mark = (
		f'<img src="{escape_html(get_url(logo))}" alt="{name}" height="32" '
		'style="display:block;height:32px;width:auto;border:0">'
		if logo
		else ""
	)
	title = f'<span style="font-size:16px;font-weight:600;color:#111827">{name}</span>' if name else ""
	return SHELL.format(
		mark=mark,
		gap=" " if mark and title else "",
		title=title,
		body=message,
		footer=escape_html(_("Sent with Frappe Sign")),
	)


def template_email(envelope: Any) -> str | None:
	"""The invitation Email Template set on the envelope's template, if any."""
	if not envelope.template_version:
		return None
	from frappe_sign.services.template import load_snapshot

	return load_snapshot(envelope.template_version).get("email_template") or None


def send(
	envelope: Any,
	recipients: list[str],
	template: str,
	context: dict[str, Any],
	*,
	attachments: list[dict[str, Any]] | None = None,
	now: bool = False,
) -> None:
	subject, message = render(template, context)
	message = wrap(message, envelope)
	reference_doctype, reference_name = reference_of(envelope)
	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		sender=sender_address(envelope.company),
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		attachments=attachments,
		now=now,
	)


def render(template: str, context: dict[str, Any]) -> tuple[str, str]:
	if frappe.db.exists("Email Template", template):
		email = frappe.get_doc("Email Template", template).get_formatted_email(context)
		return email["subject"], email["message"]
	# The fallback texts are constants in this module; values in `context` are escaped.
	subject, message = FALLBACK.get(template, FALLBACK[INVITATION])
	return (
		frappe.render_template(subject, context),  # nosemgrep: frappe-ssti
		frappe.render_template(message, context),  # nosemgrep: frappe-ssti
	)


def reference_of(envelope: Any) -> tuple[str, str]:
	if envelope.reference_doctype and envelope.reference_name:
		return envelope.reference_doctype, envelope.reference_name
	return "Sign Envelope", envelope.name


def sender_address(company: str | None) -> str | None:
	profile = company or single_profile()
	account = profile and frappe.db.get_value("Sign Profile", profile, "sender_email_account")
	return frappe.db.get_value("Email Account", account, "email_id") if account else None


def single_profile() -> str | None:
	profiles = frappe.get_all("Sign Profile", pluck="name", limit=2)
	return profiles[0] if len(profiles) == 1 else None


def notify_sender(envelope: Any, subject: str) -> None:
	"""A Desk alert for the sender. Frappe's helper inserts it for the user, whoever runs the job."""
	if not envelope.sender or envelope.sender == "Guest":
		return
	make_notification_logs(
		{
			"type": "Alert",
			"subject": subject,
			"document_type": "Sign Envelope",
			"document_name": envelope.name,
		},
		[sender_email(envelope)],
	)


def notify_user(
	user: str, subject: str, document_type: str | None = None, document_name: str | None = None
) -> None:
	"""A Desk alert for any user, such as the result of a bulk send."""
	make_notification_logs(
		{
			"type": "Alert",
			"subject": subject,
			"document_type": document_type,
			"document_name": document_name,
		},
		[frappe.db.get_value("User", user, "email") or user],
	)


def publish_realtime(envelope: str) -> None:
	status = frappe.db.get_value("Sign Envelope", envelope, ["status", "sealing_state"], as_dict=True) or {}
	frappe.publish_realtime(
		REALTIME_EVENT,
		{"envelope": envelope, **status},
		doctype="Sign Envelope",
		docname=envelope,
		after_commit=True,
	)


SHELL = (
	'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
	'style="background:#f3f4f6;padding:24px 12px"><tr><td align="center">'
	'<table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" '
	'style="max-width:560px;width:100%;background:#ffffff;border-radius:8px;'
	'font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;color:#111827">'
	'<tr><td style="padding:20px 28px;border-bottom:1px solid #e5e7eb">'
	'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
	'<td style="vertical-align:middle">{mark}</td><td style="vertical-align:middle;padding-left:10px">'
	"{title}</td></tr></table></td></tr>"
	'<tr><td style="padding:28px">{body}</td></tr>'
	'<tr><td style="padding:16px 28px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280">'
	"{footer}</td></tr></table></td></tr></table>"
)

BUTTON = (
	'<p style="margin:24px 0"><a href="{{{{ link }}}}" style="display:inline-block;'
	"background:{{{{ brand_color }}}};color:{{{{ button_text_color }}}};padding:12px 24px;"
	'border-radius:6px;text-decoration:none;font-weight:600">{label}</a></p>'
)

FALLBACK = {
	INVITATION: (
		"{{ sender_name }} sent you {{ envelope_title }} to sign",
		"<p>Hello {{ recipient_name }},</p><p>{{ sender_name }} asks you to review and sign "
		"<b>{{ envelope_title }}</b>.</p>{% if message %}<p>{{ message }}</p>{% endif %}"
		+ BUTTON.format(label="Review and sign")
		+ "<p>The link expires on {{ expires_on }}.</p>",
	),
	REMINDER: (
		"Reminder: {{ envelope_title }} is waiting for your signature",
		"<p>Hello {{ recipient_name }},</p><p><b>{{ envelope_title }}</b> is waiting for your "
		"signature.</p>"
		+ BUTTON.format(label="Review and sign")
		+ "<p>The link expires on {{ expires_on }}.</p>",
	),
	OTP: (
		"Your code for {{ envelope_title }}: {{ otp }}",
		"<p>Hello {{ recipient_name }},</p><p>Your verification code is <b>{{ otp }}</b>. It is valid "
		"for {{ minutes }} minutes. Do not share it.</p>",
	),
	COMPLETED: (
		"Completed: {{ envelope_title }}",
		"<p><b>{{ envelope_title }}</b> has been signed by everyone. The sealed PDF is attached.</p>",
	),
	DECLINED: (
		"Declined: {{ envelope_title }}",
		"<p>{{ declined_by }} declined <b>{{ envelope_title }}</b>.</p><p>Reason: {{ reason }}</p>",
	),
	VOIDED: (
		"Cancelled: {{ envelope_title }}",
		"<p>{{ sender_name }} cancelled <b>{{ envelope_title }}</b>. You do not need to sign it.</p>"
		"{% if reason %}<p>Reason: {{ reason }}</p>{% endif %}",
	),
	FAILED: (
		"Action needed: {{ envelope_title }}",
		"<p>Frappe Sign could not finish <b>{{ envelope_title }}</b> ({{ envelope }}).</p>"
		"<p>{{ reason }}</p>",
	),
}
