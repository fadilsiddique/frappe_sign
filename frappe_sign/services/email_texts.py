"""Email texts: the built-in fallbacks (English) and the Arabic versions of every template.

The Email Template fixtures (fixtures/email_template.json) hold the same texts, so a site can edit
them; tests/integration/test_events.py keeps the two in sync. An Arabic envelope uses the template
named "<name> (Arabic)" when it exists and the Arabic fallback otherwise. Values in the Jinja
context are escaped before they get here.
"""

INVITATION = "Frappe Sign Invitation"
REMINDER = "Frappe Sign Reminder"
OTP = "Frappe Sign OTP"
COMPLETED = "Frappe Sign Completed"
DECLINED = "Frappe Sign Declined"
VOIDED = "Frappe Sign Voided"
FAILED = "Frappe Sign Failed"


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


ARABIC_SUFFIX = " (Arabic)"


def arabic_name(template: str) -> str:
	return template + ARABIC_SUFFIX


RTL = '<div dir="rtl" style="text-align:right;font-family:Tahoma,Arial,sans-serif">'
BUTTON_AR = BUTTON.format(label="مراجعة وتوقيع")

FALLBACK_AR = {
	arabic_name(INVITATION): (
		"أرسل لك {{ sender_name }} المستند {{ envelope_title }} للتوقيع",
		RTL
		+ "<p>مرحباً <bdi>{{ recipient_name }}</bdi>،</p><p>يطلب منك <bdi>{{ sender_name }}</bdi> مراجعة المستند "
		"<b><bdi>{{ envelope_title }}</bdi></b> وتوقيعه.</p>{% if message %}<p>{{ message }}</p>{% endif %}"
		+ BUTTON_AR
		+ '<p>ينتهي الرابط في <bdi dir="ltr">{{ expires_on }}</bdi>.</p></div>',
	),
	arabic_name(REMINDER): (
		"تذكير: المستند {{ envelope_title }} بانتظار توقيعك",
		RTL
		+ "<p>مرحباً <bdi>{{ recipient_name }}</bdi>،</p><p>المستند <b><bdi>{{ envelope_title }}</bdi></b> بانتظار "
		"توقيعك.</p>" + BUTTON_AR + '<p>ينتهي الرابط في <bdi dir="ltr">{{ expires_on }}</bdi>.</p></div>',
	),
	arabic_name(OTP): (
		"رمزك للمستند {{ envelope_title }}: {{ otp }}",
		RTL
		+ '<p>مرحباً <bdi>{{ recipient_name }}</bdi>،</p><p>رمز التحقق الخاص بك هو <b><bdi dir="ltr">{{ otp }}</bdi></b>. '
		"صالح لمدة {{ minutes }} دقيقة. لا تشاركه مع أحد.</p></div>",
	),
	arabic_name(COMPLETED): (
		"اكتمل: {{ envelope_title }}",
		RTL
		+ "<p>وقّع الجميع على المستند <b><bdi>{{ envelope_title }}</bdi></b>. ملف PDF المختوم مرفق.</p></div>",
	),
	arabic_name(DECLINED): (
		"مرفوض: {{ envelope_title }}",
		RTL
		+ "<p>رفض <bdi>{{ declined_by }}</bdi> المستند <b><bdi>{{ envelope_title }}</bdi></b>.</p><p>السبب: <bdi>{{ reason }}</bdi></p></div>",
	),
	arabic_name(VOIDED): (
		"أُلغي: {{ envelope_title }}",
		RTL
		+ "<p>ألغى <bdi>{{ sender_name }}</bdi> المستند <b><bdi>{{ envelope_title }}</bdi></b>. لا حاجة لأن توقّعه.</p>"
		"{% if reason %}<p>السبب: <bdi>{{ reason }}</bdi></p>{% endif %}</div>",
	),
	arabic_name(FAILED): (
		"مطلوب إجراء: {{ envelope_title }}",
		RTL
		+ '<p>تعذّر على Frappe Sign إكمال <b><bdi>{{ envelope_title }}</bdi></b> (<bdi dir="ltr">{{ envelope }}</bdi>).</p>'
		"<p><bdi>{{ reason }}</bdi></p></div>",
	),
}

FALLBACK |= FALLBACK_AR
