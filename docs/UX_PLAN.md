# Frappe Sign: UX plan (Phase 2.5)

This plan makes Frappe Sign easy to understand and pleasant to use, before Phase 3. It covers the staff app (`/sign`), the guest signing page (`/s/<token>`), the verify page and the Desk touch points. The tasks are in [PLAN.md](PLAN.md), Phase 2.5. This file holds the reasons and the screen designs.

## Start here (new session)

1. Read `CLAUDE.md`, this file, `PLAN.md` Phase 2.5 and `DESIGN.md` section 7.
2. Load the skills `ui-design`, `frontend-design` and `frappe-app-dev` (its `frontend-vue.md` and `frontend-desk.md` references) before any screen work.
3. Confirm the open decisions (last section) with the user. The recommended answer is marked.
4. Look at the "before" screenshots in `docs/ux/before/`.
5. Start with U.1. Do not change screens before the user picks a direction in U.1.

## What is wrong today

The user could not find their way. These are the causes, from a screen audit on 2026-10-25.

**Nobody tells you what to do first.**

- Setup is five Desk forms: Sign Certificate, Sign Profile, Sign Settings, Sign Template and the Print Format. Nothing shows the order or what is still missing.
- The `/sign` home shows four numbers and a "Send a document" button. With an empty site, every number is 0 and there is no next step.

**Two apps, no bridge.**

- Setup and "Send for Signature" live in Desk. Requests, the send wizard and the designer live in `/sign`.
- The `/sign` header has a "Desk" link and nothing else. The Desk sidebar lists 12 raw DocTypes, including internal ones such as Sign Capture, Sign Session and Sign Template Version.

**Our words, not the user's.**

- The UI says Envelope, CC, Party Contact, Doc Field, Fixed User, Ask at Send, OTP mode, TSA URLs and Anchor tag.
- The post-sign action is a JSON field.

**Dead ends.**

- `/sign/templates` and the designer make only "Uploaded PDF" templates. The DocType field never appears, so a user cannot make a Quotation template there. The user hit exactly this.
- The "From a document" card in the send wizard has two plain text boxes. You must type `Quotation` and the exact document number from memory.
- `/sign/settings` is listed in DESIGN 7.2 but does not exist.

**Bland, unfinished look.**

- Every page is a white box on gray with small type and a lot of empty space. There are no icons, no empty states, no loading skeletons and no thumbnails.
- The request detail does not show the document.
- The guest consent screen shows a radio-looking circle for a checkbox and a gray, disabled-looking button. The signing screen has no branding and "1 required fields left".
- The Desk send dialog has a checkbox column that does nothing useful, and a large empty message box.

## Design direction

The register is product clarity, not marketing. Frappe Sign should feel like Frappe's own newer apps (CRM, Helpdesk, Gameplan): calm, dense where it helps, with one clear primary action per screen.

- **Shell:** frappe-ui `Sidebar` with the app name and the company logo at the top. Below it: Home, To sign, Sent, Templates, Settings, then "Back to Desk" at the bottom. A user menu sits at the bottom. On phones, `MobileShell` and `MobileNav`.
- **Type:** frappe-ui scale. Page titles 20px semibold, body 14px, secondary text 13px gray-6 or darker. Nothing under 12px except badges.
- **Color:** neutral surfaces. Color only for status badges and role colors. On the guest page only, the company brand color comes from the Sign Profile.
- **Surfaces:** fewer boxed cards. Lists are full-width rows with dividers. Use a card only where the content is a separate object, such as a template thumbnail.
- **Icons:** lucide icons through frappe-ui, never emoji.
- **States:** every list and page gets an empty state that says what to do next, a `Skeleton` while loading, and an inline error with a retry. Use toasts instead of `msgprint` in the staff app.
- **Lanes:** in every list, the avatar, status and action columns have fixed widths and line up from row to row.

### Words

These are UI labels only. DocType names, fields and APIs stay as they are (D13).

| Today | New label |
| --- | --- |
| Envelope | Signature request (short: Request) |
| Envelopes | Sent (staff nav), Requests (lists) |
| CC | Gets a copy |
| Signer / Approver | Signs / Approves |
| Party Contact | The customer or supplier on the document |
| Doc Field | A person named in a field of the document |
| Fixed User | A specific person |
| Ask at Send | Chosen when sending |
| OTP mode: Email OTP / Off | Verify with an emailed code: On / Off |
| Delegate | Pass to someone else |
| TSA URLs | Timestamp servers (Advanced) |
| Post sign action + JSON | After everyone signs: a plain list of choices |
| Sealing certificate | Company seal |

## Screens

### Home `/sign`

- **Until setup is done:** a "Get started" checklist at the top. Each step shows Done or To do and opens the right place:
  1. Email account
  2. Company seal (certificate)
  3. Company profile
  4. Documents you sign (enabled DocTypes)
  5. First template
  6. Send a test
- **"Needs your signature":** rows with document title, sender, how long ago, and a **Sign** button that opens `/s/<token>`.
- **"Waiting on others":** rows with title, an avatar stack of signers with done ticks, "2 of 3 signed", the sent date and the expiry.
- **Small figures:** completed this month and expiring soon, as plain text, not cards.
- **Primary action:** "New request".

### Sent `/sign/requests` (today `/sign/envelopes`; keep a redirect)

- A table with these columns:
  - Document, with its DocType and number below
  - Recipients, as avatars with a status ring each
  - Progress, for example "1 of 2"
  - Status badge
  - Sent date
  - Expires
- Search box. Tabs with counts: All, Waiting, Drafts, Completed, Closed.
- Filters: DocType, sender, date.
- Each row opens the detail. Row actions (Remind, Copy link, Void) go in a menu at the end of the row.

### Request detail

- **Left, wide:** the PDF, with the signed values once there are any.
- **Right panel:**
  - Status, title and source document link
  - Recipients as a vertical step list, with who signed when, who is next, and their per-person actions (Remind, New link)
  - A primary action that fits the state: Remind while waiting, Download signed PDF when completed
  - Other actions in a menu: Void, Original PDF, Certificate, Verify
- **Activity:** a timeline in plain words ("Ahmed Khan opened the document · 2 h ago"). The full audit trail with hashes sits behind "Show audit details". "Hash chain verified" becomes a small shield icon with a tooltip.

### New request (send wizard) `/sign/new`

- **Step 1, Document.** Three large choices with icons:
  - **From an ERPNext document:**
    - A DocType picker that lists only enabled DocTypes.
    - A searchable document picker (`Combobox`) that shows the number, party, date and total, for example `SAL-QTN-2026-00023 · Gulf Trading LLC · AED 71.00`.
    - Picking a document chooses the default template.
  - **From a template:** cards with a page thumbnail and the type ("Print Format" or "Own PDF").
  - **Upload a PDF:** a drop zone.
- **Step 2, People.** One row per role:
  - The role name and a "Signs" or "Gets a copy" chip.
  - Name and email with autocomplete from Contacts and Users.
  - A tick when the person was found from the document.
  - The order shown as numbers with "Sign in this order" or "All at once".
- **Step 3, Check.** The PDF with every field box labelled by person, and a warning list for anything missing.
- **Step 4, Send.** Message (optional, collapsed), expiry and reminders, then **Send**.
- **Footer:** sticky Back and Next. A stepper at the top shows the steps done.

### Templates `/sign/templates`

- A grid of cards: page thumbnail, title, DocType chip, type chip, Published or Draft, last used.
- **New template** asks the kind first, with two cards:
  - **"For an ERPNext document (Print Format)"** opens a form in the staff app. Desk is no longer the main path. It has:
    - DocType picker, then Print Format picker. The picker shows "Has signature fields" or "No signature fields yet, see the anchor guide".
    - People: role name and who signs, in the words above.
    - After everyone signs: None, Submit the document, Create a draft Sales Order (shown for Quotation), Set a field, Apply a workflow action. The app builds the JSON.
    - Preview with a real document.
    - Publish.
  - **"Your own PDF"** opens the designer.
- The Desk Sign Template form gets an intro: "Easier in Frappe Sign", with a link to the staff editor.

### Designer

- **Empty canvas:** a drop zone for the PDF, not a gray area with a sentence.
- **Palette:** icons, grouped as Signature (Signature, Initials, Company stamp) and Details (Name, Email, Date, Text, Number, Checkbox, Dropdown, Attachment).
- **People panel:** compact, with the role color dot, the name and who signs. Details expand on click.
- **Header:** title, save state ("Saved" or "Unsaved"), Undo and Redo as icons, then Publish as the primary button.

### Settings `/sign/settings` (new)

- **Company tab:** one card per Sign Profile, with:
  - Logo and color
  - Sender email and its status (connected, or missing)
  - Signs for the company
  - Seal status: "Self-signed, valid until 24 Oct 2029", or "Missing", with **Create test seal** and **Upload certificate** buttons
- **Documents tab:** enabled DocTypes, with the default template and the number of sends per DocType. Add one with a picker (System Manager).
- **Signing tab:** expiry, reminders, emailed code, consent text.
- **Advanced tab:** timestamp servers. The Phase 3 health panel (P3.7) goes here later.
- **Permissions:** a Sign Manager can see Settings. A System Manager can change everything.

### Guest signing `/s/<token>` (phone first, 390 px)

- **Header:** company logo and name from the Sign Profile, then the document title.
- **Consent:** a clear checkbox, and the primary button in the brand color once the box is ticked. Show "From Gulf Trading LLC" with the sender's name.
- **Signing:**
  - A slim progress bar ("1 of 2 done").
  - A floating "Next: Signature" button that jumps to and highlights the next field.
  - Fields in the brand color, with clear states: to do, done, optional.
  - Delegate and Decline go into a "More" menu.
- **Signature sheet:** Type is prefilled with the signer's name. A baseline on the Draw canvas. A large Save button.
- **Finish:** a review list of what was filled, then **Finish and sign**.
- **Done screen:** a tick, "You signed E2E Service Agreement", "Everyone will get the signed PDF by email", and a Download button once it is sealed.
- **Terminal screens** (Declined, Expired, Voided, Waiting): the same layout with an icon and one sentence.
- **Budget:** under 250 KB gzipped. Check after each change.

### Verify `/sign-verify`

- A drop zone, or "Enter request ID".
- The result is a card: a green tick or a red cross, the signers, the times, and the seal owner.

### Desk touch points

- **Send dialog:** recipients as plain rows (role, name, email) without the checkbox column. The message box is collapsed behind "Add a message". Customize is relabelled "Preview and edit".
- **Workspace and sidebar:** the Signatures workspace with shortcuts to Open Frappe Sign, New request, Settings and Get started. The sidebar shows Sign Envelope (labelled Requests), Sign Template, Sign Trigger and Sign Settings only. Internal DocTypes (Sign Event, Capture, Session, Saved Signature, Template Version, Trigger Log) leave the sidebar and stay reachable through search.
- **Form headline:** keep "Signature: Sent" and add who it is waiting for.

### Emails

- The invitation, reminder, completed and declined emails get the company logo, one button in the brand color and a short plain message. They stay table-based HTML for email clients.

## Quality bar

Each screen task is done only when all of these hold:

- **Design review:** the `ui-design` checklist (spacing, typography, contrast, alignment, fit, repetition) passes on screenshots at 1440 px and 390 px. Before and after screenshots go in `docs/ux/after/`.
- **Language:** Arabic (`dir="rtl"`) does not break the layout. Tailwind logical properties only.
- **Accessibility:** keyboard reachable, visible focus, ARIA labels on canvas fields, WCAG AA contrast.
- **Tests:** the existing Playwright specs pass. Update `data-testid` use only where the screen changed, and add one spec per new screen.
- **Stale browsers:** test with a browser that has used the old version too, not only a fresh Playwright profile. Desk scripts stay in `.bundle.js` files.
- **Sizes:** the guest bundle stays under 250 KB gzipped.
- **Copy:** no em dashes.

## Open decisions (confirm at the start of the session)

1. **Call an envelope a "Signature request" in the UI.** Recommended. DocType names stay (D13).
2. **Move setup and Print Format template creation into the staff app,** and keep the Desk forms for admins. Recommended. Users then need Desk only for the "Send for Signature" button.
3. **App shell:** frappe-ui `Sidebar` like CRM and Helpdesk (recommended), or a top bar as today.
4. **Brand color:** the company brand color on the guest page and the emails only. The staff app stays neutral. Recommended.
5. **Route rename** `/sign/envelopes` to `/sign/requests`, with a redirect. Recommended, since emails and Desk links use the old path.
