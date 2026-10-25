# Frappe Sign: Admin guide

This guide is for the System Manager who sets up Frappe Sign on a site. It covers what the site needs, the setup in order, and what to check when something fails.

## What the site needs

- Frappe v16 (ERPNext v16 for the ERPNext features). Any v16 release works.
- Background workers for the `default`, `short` and `long` queues, and the scheduler. Frappe Sign renders, seals and writes back in jobs. Without workers, envelopes stay in "Sending" or "Sealing".
- A PDF generator for your Print Formats: wkhtmltopdf (patched Qt build), or Chromium for Print Formats that use the `chrome` generator. Frappe downloads Chromium the first time it needs it.
- Outbound network access from the workers to the timestamp servers (TSA). The defaults are the public DigiCert and Sectigo servers.
- An outgoing Email Account.

After you update the app, restart the web server and the workers. A process that runs old code sends jobs that the new code cannot run.

## Roles

| Role | Can |
| --- | --- |
| Sign Manager | Profiles, templates, triggers, all envelopes |
| Sign User | Send envelopes from published templates, see the envelopes they sent or must sign |
| System Manager | Everything a Sign Manager can do, plus certificates and the DocTypes enabled for signing |

A sender also needs read and print permission on the documents they send, for example Sales User for Quotations.

## Setup

Do these steps in order.

### 1. Email Account

1. Create an outgoing Email Account for the company, for example `sign@yourcompany.com`.
2. Send a test email from it.

Set up SPF and DKIM for the domain. Without them, invitations often land in spam.

### 2. Sealing certificate

1. Open **Sign Certificate** and click **New**.
2. Attach the `.p12` file and enter its password.
3. Save. Frappe Sign checks the file, the password and the dates.

A self-signed certificate seals the PDF, but Adobe Reader shows it as "validity unknown". For a green tick in Adobe Reader, buy an AATL document-signing certificate.

### 3. Sign Profile

1. Open **Sign Profile** and click **New**.
2. Select the **Company**.
3. Select the **Sealing certificate** and the **Sender email account**.
4. Set the **Authorised signatory**. This user signs for the company when a template role is "Fixed User" without a user.
5. Add the logo, brand color and legal footer. They appear on the signing page and on the certificate of completion.

Make one Sign Profile for each company.

### 4. Sign Settings

1. Open **Sign Settings**.
2. Under **Enabled DocTypes**, add each DocType you will send, for example Quotation. Saving adds two fields to it: **Signature Status** and **Signature Envelope**. Only a System Manager can add a DocType.
3. Set the default template for each DocType, if you have one.
4. Check the expiry days, reminder days and OTP validity.
5. Add your own TSA URLs if your policy needs them, one per line.
6. Replace the consent text with the text your lawyer approves.

When you take a DocType off the list, its fields and values stay. To delete the fields, a System Manager calls `frappe_sign.api.staff.remove_sign_fields` with the DocType.

### 5. Print Formats

Add `sign_field()` to each Print Format you will send. See [ANCHOR_GUIDE.md](ANCHOR_GUIDE.md).

### 6. Templates

Make a Print Format template in Desk. The designer at `/sign/templates` is for uploaded PDFs, where you place the fields by hand.

1. Open **Sign Template** in Desk and click **New**.
2. For **Source type**, select **Print Format**. Then select the **DocType**, the **Print format** and the **Company**.
3. Add a role for each party. Select how Frappe Sign finds each signer:

| Signer source | Finds |
| --- | --- |
| Party Contact | The customer, supplier or other party of the document, and its contact |
| Doc Field | The value of a field: an email, or a link to a User, Contact, Customer, Employee and similar |
| Employee | The document's Employee |
| Fixed User | The user you select, or the authorised signatory of the Sign Profile |
| Ask at Send | Nobody. The sender types the name and email |

4. Set the signing order, the verification (Email OTP or Off) and the expiry.
5. Leave the **Fields** table empty: each `sign_field()` in the Print Format becomes a field. Add a row only to change a field, for example to make a date optional. Set its **Anchor tag** to the marker, for example `[[fs:Customer:date_signed:1]]`, and **Page** to 0.
6. Save, then click **Publish**. Senders see only published templates. After each change, publish again.

### 7. Post-sign action (optional)

A template can run one action after everyone signs. The action runs in a job as the sender, with the sender's permissions. If it fails, the signature stays valid. Frappe Sign writes the error to the Error Log and the audit trail, and notifies the sender.

For "Quotation signed, make a draft Sales Order":

- **Post sign action**: Create Mapped Document
- **Post sign config**:

```json
{
  "method": "erpnext.selling.doctype.quotation.quotation.make_sales_order",
  "save": 1,
  "values": {"delivery_date": "today+7"}
}
```

ERPNext's Sales Order needs a Delivery Date, and the mapper does not set one. `today+7` sets it 7 days ahead. Config values accept `today`, `today+N`, `today-N` and `now`.

The method must be a whitelisted function.

### 8. Triggers (optional)

A Sign Trigger creates or sends an envelope when a document event happens, for example "on Submit of a Quotation".

A trigger runs as its owner: the Sign Manager who created it. The owner must be able to read and print the documents. In "Send" mode, the envelope is sent only when every signer has a name and an email. Otherwise it stays a draft, and the owner gets a notification.

Each run writes a **Sign Trigger Log**. A failed run also adds a comment to the document.

## Sending

- From the form: **Send for Signature**. The dialog fills the recipients from the document. Check them, then click **Send**.
- From the print view: **Send for Signature** sends the Print Format and Letter Head on screen.
- From the list view: select documents, then **Actions > Send for Signature**. Documents without an email for a signer are skipped. A notification lists them.
- **Customize** in the dialog opens the send wizard. It shows the PDF with the fields before you send.

The document shows **Signature: Sent**, then **Partially Signed** and **Signed**. When everyone signs, the sealed PDF is attached to the document.

## When the document changes

- Cancel or delete the document: Frappe Sign voids its open envelopes and tells the signers.
- Edit the document while an envelope is open: Frappe Sign marks the envelope "source changed" and notifies the sender. The envelope keeps the PDF that was sent. To send the new version, void the envelope and send again.

## Security notes

- The signing link contains a token. Web server access logs record it. Keep those logs private and short-lived.
- Every PDF that Frappe Sign stores is a private file.
- If you change the site's `encryption_key`, every open signing link stops working. Use **New link** on each open envelope.

## Troubleshooting

| You see | Do this |
| --- | --- |
| "Send failed" on the envelope | Read the reason. A missing `sign_field()` for a required field, a Print Format error or a missing PDF generator are the usual causes. Fix it and send again |
| The envelope stays "Sending" | Start the workers |
| "Sealing failed" | Frappe Sign retries after 1, 5 and 30 minutes. Check the Error Log "Frappe Sign: seal": usually the TSA cannot be reached or the certificate expired. A Sign Manager can click **Retry seal** |
| No invitation email | Check the Email Account and the Email Queue. Use **Remind** or **New link** on the envelope |
| A trigger did nothing | Open the Sign Trigger Log for the document. "Skipped" shows the reason |
| The post-sign action did not run | Open the envelope's audit trail. A "Post-Sign Action" event shows the error |

`bench --site <site> frappe-sign verify <envelope>` checks the audit chain and the file hashes of an envelope.
