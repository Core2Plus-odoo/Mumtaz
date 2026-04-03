# Mumtaz Static Website (`/website`)

This folder contains the **independent static website** for **https://mumtaz.digital**.

It is designed for direct deployment to **Hostinger** with **no build step** and does **not** depend on the Odoo backend runtime.

## Purpose

- Public-facing premium website for Mumtaz
- Clear product positioning across ERP, AI CFO, and embedded finance
- Easy to zip and upload to Hostinger `public_html`
- Fully isolated from backend/Odoo modules

## Folder Structure

```text
apps/website/
  index.html
  platform.html
  erp.html
  ai.html
  finance.html
  banks.html
  smes.html
  demo.html
  about.html
  contact.html
  assets/
    css/
      style.css
    js/
      main.js
    images/
  README.md
```

## Homepage

- Homepage file: `index.html`

## Where to Edit Common Content

- **Demo links**:
  - `demo.html`
  - `ai.html`
  - `finance.html`
  - `banks.html`
  - `smes.html`

  Current placeholders:
  - https://demo.mumtaz.digital
  - https://demo.mumtaz.digital/sme
  - https://demo.mumtaz.digital/ai
  - https://demo.mumtaz.digital/partner

- **Emails / contact details**:
  - `contact.html`
  - Footer in each page

  Current placeholders:
  - `hello@mumtaz.digital`
  - `partnerships@mumtaz.digital`

- **Branding assets**:
  - Place logo/favicon/og image in `assets/images/`
  - Update image references in page `<head>` blocks as needed

## Hostinger Deployment (`public_html`)

1. Zip the **contents of `/website`**.
2. Open Hostinger File Manager for `mumtaz.digital`.
3. Navigate to `public_html`.
4. Upload and extract website files.
5. Ensure `public_html/index.html` exists.
6. Visit `https://mumtaz.digital` and validate navigation.

## Relative Path Notes

- Internal pages link relatively (example: `platform.html`, `contact.html`).
- Shared static assets use:
  - `assets/css/style.css`
  - `assets/js/main.js`
  - `assets/images/...`

This keeps deployment compatible with direct static hosting in `public_html`.

## Independence from Odoo Backend

This folder is intentionally separate from Odoo code and does not modify addons, manifests, Python imports, or runtime behavior.
