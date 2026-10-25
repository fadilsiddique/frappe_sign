# Frappe Sign: Print Format anchor guide

This guide is for people who write Jinja Print Formats. It shows how to mark the places where signers sign.

## How it works

You put `sign_field()` in the Print Format where a signer must sign, initial or fill in a value. When Frappe Sign sends the document, it renders the Print Format to a PDF. Then it finds each `sign_field()` in that PDF and puts a field there for the signer.

The fields follow the content. When a Quotation has 40 items instead of 3, the signature box moves to the next page, and the field moves with it.

## Add a field

Put the call in the Print Format HTML:

```jinja
{{ sign_field("signature", role="Customer", width=60, height=20) }}
```

The arguments:

| Argument | Meaning |
| --- | --- |
| field type (first argument) | `signature`, `initials`, `company_stamp`, `full_name`, `email`, `date_signed`, `text`, `number`, `checkbox` or `dropdown` |
| `role` | The template role that fills the field, for example `Customer` or `Company` |
| `width`, `height` | The size of the box in mm. Each field type has a default size |
| `border` | `True` draws a dotted box, so the printed document shows where to sign |
| `n` | A number that tells two fields of the same type and role apart. Without it, Frappe Sign counts them from 1 in each render |

The default sizes in mm:

| Type | Width x height |
| --- | --- |
| `signature` | 60 x 20 |
| `initials` | 25 x 15 |
| `company_stamp` | 40 x 40 |
| `full_name`, `email`, `text` | 60 x 8 |
| `date_signed`, `dropdown` | 40 x 8 |
| `number` | 30 x 8 |
| `checkbox` | 6 x 6 |

## Example: a Quotation

```jinja
<table style="width: 100%; margin-top: 10mm; page-break-inside: avoid;">
  <tr>
    <td>
      Customer<br>
      {{ sign_field("signature", role="Customer", width=60, height=20, border=True) }}<br>
      Date: {{ sign_field("date_signed", role="Customer") }}
    </td>
    <td>
      For {{ doc.company }}<br>
      {{ sign_field("signature", role="Company", width=60, height=20, border=True) }}
    </td>
  </tr>
</table>
```

`page-break-inside: avoid` keeps the signature block on one page.

## Roles

The `role` must match a role label in the Sign Template. Spaces in the label become `_`. For example, the role `Sales Manager` is written `role="Sales Manager"` and appears in the PDF as `Sales_Manager`.

Use Latin letters, digits, spaces, `-` and `_` in role labels. An Arabic role label cannot be used in `sign_field()`.

## What happens at send

1. Frappe Sign renders the Print Format with its own PDF generator.
2. It finds every `sign_field()` in the PDF.
3. A template field with the same anchor gets its place from the anchor.
4. An anchor without a template field becomes a new field for the Signer with that role. Signature, initials and company stamp fields are required. The other types are optional.
5. If a required template field has no anchor in the PDF, the send fails and the sender sees the reason.
6. An anchor for a role that has no Signer in the envelope stays empty.

## Check your Print Format

1. Open the document in Desk and click **Send for Signature**.
2. Click **Customize**.
3. Go to the **Preview** step. Each field shows as a box with its role and type.
4. Make sure each box covers the place where the signer must sign.

The preview also lists roles that have no signer.

## PDF generators

Anchors are tested with the `wkhtmltopdf` and `chrome` generators. Set the generator on the Print Format (**PDF Generator**). If a Print Format uses another generator, the preview shows a warning. Check the places of the fields before you send.

## Rules that prevent problems

- Do not put `sign_field()` inside an element with `overflow: hidden`, `display: none` or a transform.
- Do not put it in a page header or footer. A header repeats on every page, and only the first anchor counts.
- Use a white background behind the field. Frappe Sign paints the field area white before it draws the value.
- Do not scale the content with CSS `zoom` below 50% or above 200%. Frappe Sign scales the field with the content only inside that range.
- A wrong argument stops the print with a "Print Format error". Fix the call and print again.
