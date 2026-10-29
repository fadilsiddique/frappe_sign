# Frappe Sign: UX plan (Phase 2.5)

This plan makes Frappe Sign easy to understand and pleasant to use, before Phase 3. It covers the staff app (`/sign`), the guest signing page (`/s/<token>`), the verify page and the Desk touch points. The tasks are in [PLAN.md](PLAN.md), Phase 2.5. This file holds the reasons and the screen designs.

## Start here (new session)

1. Read `CLAUDE.md`, this file, `PLAN.md` Phase 2.5 and `DESIGN.md` section 7.
2. Load the skills `ui-design`, `frontend-design` and `frappe-app-dev` (its `frontend-vue.md` and `frontend-desk.md` references) before any screen work.
3. Read the confirmed decisions (last section, and D18 in DECISIONS.md). Do not ask again.
4. Look at the "before" screenshots in `docs/ux/before/`.
5. U.1 is done: the user chose a direction (see "Chosen direction" below). Build from this file, not from the prototype's other direction.

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

- **Shell (D18):** frappe-ui `Sidebar` with the app name and the company logo at the top. Below it: Home, To sign, Sent, Templates, Settings, then "Back to Desk" at the bottom. A user menu sits at the bottom. On phones, `MobileShell` and `MobileNav`.
- **Type:** frappe-ui scale. Page titles 20px semibold, body 14px, secondary text 13px gray-6 or darker. Nothing under 12px except badges.
- **Color:** neutral surfaces. Color only for status badges and role colors. On the guest page only, the company brand color comes from the Sign Profile.
- **Surfaces:** fewer boxed cards. Lists are full-width rows with dividers. Use a card only where the content is a separate object, such as a template thumbnail.
- **Icons:** lucide icons through frappe-ui, never emoji.
- **States:** every list and page gets an empty state that says what to do next, a `Skeleton` while loading, and an inline error with a retry. Use toasts instead of `msgprint` in the staff app.
- **Lanes:** in every list, the avatar, status and action columns have fixed widths and line up from row to row.

### Chosen direction (U.1, 2026-10-25)

The U.1 prototype showed two directions on a Design canvas (https://claude.ai/artifact/8cAiSfS9KB1HoEwjzV3tis, private to the user). The user chose:

- **Staff app: Direction B, "Guided desk".**
  - The page area is gray-50 with white panels. The sidebar is white, and the active item has a gray-200 background.
  - Each page has a 48 px header bar, level with the sidebar header, with the title and the primary action. On phones, the primary action is an icon button in the header, and other actions sit in a row under it.
  - Home puts the work queue beside a setup panel. Sent puts a grouped list beside a preview pane.
  - Defaults: comfortable density, list layout, full row detail. The board view (Sent by stage, as columns) is not in scope.
- **Guest page: Direction A, "Quiet list".**
  - The document comes first, under a white header with the company logo and name.
  - The consent is a bottom sheet over the document.
  - The other parts: a slim progress bar, a floating "Next" button, a signature bottom sheet, a review list and a done screen.

The words, tokens and states in this section apply to both.

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

Two columns: the work queue (wide) and a side panel (320 px). The side panel goes under the queue on narrow screens.

- **Until setup is done, the side panel is "Set up signing":** numbered steps joined by a line. A done step shows a tick and a one-line summary, such as "Self-signed, valid until 24 Oct 2029". The first open step is expanded, with one sentence and its button, and that button is the page's primary action. Any step expands on click. The steps:
  1. Email account
  2. Company seal (certificate)
  3. Company profile
  4. Documents you sign (enabled DocTypes)
  5. First template
  6. Send a test

  The server (`get_setup_status`) reports what is done and who may fix each step; the staff app words it. "Documents you sign" counts only with ERPNext. Until Settings exists (U.9), steps 1 to 4 open their Desk forms.
- **After setup, the side panel shows:**
  - This month: Completed, Waiting and Declined, as figures in one panel, not as separate cards.
  - Expiring soon: each request, who has not signed, and a Remind button.
  - A seal status line: "Company seal valid until 24 Oct 2029".
- **"For you to sign" panel:** rows with a page thumbnail, the title, "Ahmed Khan asked you to approve, 2 hours ago", the role ("You sign" or "You approve") and a **Sign** or **Approve** button that opens `/s/<token>`.
- **"Waiting on others" panel:** grouped as "Waiting on customers and suppliers" and "Waiting on your team". Each row has:
  - The title, and "Next: Omar Farouk, opened it 3 hours ago".
  - Numbered order dots: green when signed, blue for the next person.
  - "1 of 2", and the expiry.
- **Empty states:** "You are all caught up" and "Nothing sent yet", each with the next step.
- **Primary action:** "New request" once setup is done. Before that, it is an outline button.
- **Sidebar:** "To sign" has a count badge. While setup is open, "Settings" shows "3 left".

### Sent `/sign/requests` (today `/sign/envelopes`; keep a redirect)

A split view: the list on the left (about 400 px) and a preview of the selected request on the right. The preview goes under the list on narrow screens.

- **Toolbar:** filter pills with counts, then a search box (title, document number, person) and a Filter button that opens a row of choices: document type, sent by (when more than one sender), and a from and to date (the day the request was made). The pills are Open, Completed, Closed and All. Open is the default, and it holds waiting requests and drafts.
- **List:** grouped under headings with counts: Waiting on customers and suppliers, Waiting on your team, Drafts, Completed, Closed.
  - Each row: the title, the "Next: ..." line, the progress ("1 of 2") and a short expiry ("Ends 5 Nov", amber when it ends in 3 days or less).
  - The selected row has a gray background and a dark bar at its start edge. The keyboard moves the selection.
- **Preview pane:**
  - The status badge, "Sent 22 Oct by Mariam Haddad", the title, and the source document as a link.
  - The primary action, which fits the state: Remind (waiting), Download signed PDF (completed), Send (draft) or Send again (declined, voided, expired). Other actions go in a menu: Original PDF, Certificate, Retry seal and Void request (which asks for a reason).
  - There is no "Copy link": a signing link works as the recipient, so showing it to the sender would weaken D10. The sender can send a new link to one person (New link).
  - A page thumbnail, beside the people as a step list. The heading says "People, in signing order" or "People, all at once". Each person shows the role in plain words, the state and the time. Remind and New link appear on the person who is next.
  - Activity in plain words, with a "Verified" shield and "Show audit details".
- **Open the full detail (U.5):** the title in the preview opens `/sign/requests/<id>`.

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
- **Signature sheet:** Type is prefilled with the signer's name. A baseline on the Draw canvas. A large Save button. A press that starts while the sheet slides in must not close it (today a stroke started mid-slide lands on the backdrop and closes the sheet; found in U.2).
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

## Decisions (confirmed by the user on 2026-10-25, recorded as D18)

1. The UI calls an envelope a "Signature request" ("Request" for short). DocType names stay (D13).
2. Setup and Print Format template creation move into the staff app. Desk keeps its forms for admins and the "Send for Signature" button.
3. The app shell is a frappe-ui `Sidebar`, like CRM and Helpdesk.
4. The company brand color appears on the guest page and in emails only. The staff app stays neutral.
5. `/sign/envelopes` becomes `/sign/requests`, with a redirect from the old path.
6. U.1 direction (confirmed 2026-10-25): Direction B "Guided desk" for the staff app, Direction A "Quiet list" for the guest page. See "Chosen direction".
