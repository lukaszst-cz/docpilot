# 📂 DocPilot

**Documents + Deadlines + Actions + Archive — local-first.**

DocPilot turns mixed folders of scans, PDFs, receipts, invoices, contracts and letters into a searchable local archive that can detect deadlines, propose actions, organize files and keep a reversible audit trail.

> Analyze locally. Review before applying. Keep control of the originals.

![DocPilot demo](assets/demo.gif)

## Download for Windows

**Product page for testers:** https://lukaszst-cz.github.io/operations-office-portfolio/docpilot/

**Direct Windows installer:** https://github.com/lukaszst-cz/docpilot/releases/download/v0.5.1/DocPilot-Setup-Windows-x64.exe

For non-technical users, use the product page or the repository **Releases** page:

- `DocPilot-Setup-Windows-x64.exe` — normal Windows installer;
- `DocPilot-Portable-Windows-x64.zip` — unpack and run `DocPilot.exe`;
- `SHA256SUMS.txt` — release checksums.

The Windows release workflow is configured to bundle the application, background deadline notifier, Tesseract OCR and Polish/English OCR data. A release artifact is only available after the workflow has successfully built on a Windows runner.

Developers/testers can run the source version with `DocPilot.bat`.


## Repository layout

The public repository intentionally keeps documentation simple. `README.md` is the only Markdown documentation file because GitHub renders it automatically on the project home page. Release notes live in GitHub Releases rather than as extra files in the repository.

## One-click safe demo

On a fresh installation the Dashboard offers **Try safe demo**. It loads a bundled synthetic invoice into DocPilot so a tester can see classification, deadline detection, indexing and search without selecting a private file.

The demo never reads or modifies the tester's own documents.

## Core principles

- **Local-first:** core OCR, indexing, vector search, Q&A and file operations run on the local computer.
- **Preview-first:** DocPilot proposes a category, filename and action before a change is applied.
- **Verified file operations:** rename/move operations are checked on disk before success is reported.
- **Undoable:** reversible changes are stored in local history.
- **Human-in-the-loop:** uncertain documents are surfaced in **Review Queue** instead of being silently trusted.
- **Optional cloud integrations:** Gmail/Outlook IMAP, Notion and Google Calendar are opt-in.

## Features

### Smart Inbox

- native Windows file picker for real-file operations;
- drag-and-drop safe-copy import;
- local OCR for images and scanned PDFs;
- classification, metadata extraction and automatic tags;
- suggested category and filename;
- verified rename or smart archive move;
- smart archive structure such as `Finance/Invoices/2026/Company`;
- batch import and Watch/Scanner Folder.

### Scan Cleaner + OCR

- EXIF orientation handling;
- OCR orientation detection when available;
- deskew with OpenCV;
- grayscale, autocontrast and light denoise cleanup;
- scanned-PDF page rendering and OCR when a useful text layer is missing;
- PL+EN OCR in Windows release builds;
- QR detection through OpenCV; optional broader barcode support with `pyzbar`.

### Deadline Radar

Detects and tracks, where clearly present:

- payment deadlines;
- response deadlines;
- validity/expiration dates;
- warranty dates;
- vehicle/inspection-related dates;
- contract dates and notice-period information.

Documents can be marked as:

`to-pay` · `to-reply` · `to-sign` · `to-review` · `to-archive`

### Review Queue

Documents are automatically queued for human review when DocPilot detects:

- low extraction confidence;
- poor scan/document health;
- deadline wording without a confidently extracted date;
- possible exact or near duplicate;
- missing searchable text;
- explicit `to-review` action.

### Receipt / Invoice / Warranty / Contract modes

DocPilot can extract or infer fields such as:

- issuer/contractor;
- date;
- amount/currency;
- invoice/reference number;
- NIP;
- IBAN;
- VAT rate;
- net/gross amount where clearly present;
- payment deadline;
- warranty duration/end date;
- notice period;
- automatic-renewal wording.

### Duplicate Finder

- exact duplicates: SHA-256;
- near duplicates: local text fingerprint.

DocPilot never auto-deletes duplicates.

### Document Diff

Compare two versions of a document and inspect:

- similarity;
- added lines;
- removed lines;
- unified text diff.

### Cases & Timeline

Group related documents into a case such as:

- insurance claim;
- court/administrative case;
- school matter;
- contract/complaint;
- vehicle matter.

The timeline shows document dates, deadlines and actions chronologically.

### Local vector search

Search is local and model-free by default. DocPilot uses a dense local vector-space representation based on TF-IDF + latent semantic analysis, mixed with lexical/synonym scoring. No document or query is sent to a remote model.

Example:

```text
pokaż dokumenty dotyczące zalania mieszkania
```

can rank documents containing related insurance/water-damage language even when filenames differ.

### Local Q&A

Local Q&A supports structured questions such as:

- `jaki jest najbliższy termin?`
- `które pisma wymagają odpowiedzi?`
- `ile łącznie wynoszą wykryte kwoty w dokumentach dotyczących szkody?`
- `kiedy kończy się gwarancja?`

For open questions DocPilot uses extractive answers from locally ranked documents. It does not invent facts beyond the indexed source text. Important information should be checked against the original document.

### Sensitive Data Detector + Redaction

Detection includes likely:

- PESEL;
- NIP;
- IBAN;
- email addresses;
- phone numbers;
- address-like strings.

Redaction always creates a separate copy. It supports:

- text files;
- searchable PDFs;
- images using OCR coordinates;
- scanned PDFs by rasterizing pages, OCRing them and rebuilding a redacted image-based PDF.

**Always visually review a redacted copy before sharing it.**

### Rules Engine, profiles and custom document types

Profiles can separate contexts such as:

`Home` · `Company` · `Child` · `Vehicle` · `Legal Cases`

Example rule:

```text
if issuer contains "Orange"
→ Finance/Telecom
→ profile: Home
```

Custom types let users define their own keywords and destination category.

### Email attachments

Two options:

- import attachments from an exported `.eml` file;
- optional direct Gmail/Outlook IMAP connector.

Direct mailbox credentials are stored via the operating-system keyring. For Gmail/Outlook use an app password or provider-supported credential, not your main account password.

### Background deadline notifications

The Windows package includes a lightweight `DocPilotNotifier.exe` helper. It can be registered at Windows sign-in and check locally indexed deadlines even when the main DocPilot window is closed.

### Calendar

- `.ics` export works without an account;
- optional direct Google Calendar sync through the user's own OAuth desktop client file.

### Notion

- CSV export works without an API connection;
- optional direct Notion database sync using the user's own integration token.

### Obsidian

Exports Markdown notes with YAML-like metadata and source paths in a ZIP ready for a vault/import workflow.

### Backups

- **Index Backup:** SQLite index + metadata, no source files;
- **Full Archive Backup:** index + metadata + copies of source documents that are still accessible.

A manifest records missing/unreadable source files instead of failing the entire backup.

### Audit Log + Full Undo History

DocPilot records file actions, imports, sync actions, redactions and automation events locally. Reversible rename/move actions can be undone from history.

### MCP server (optional)

```bash
python -m docpilot.mcp_server
```

Compatible local MCP clients can use DocPilot search and Q&A tools without exposing the archive through a public server.

## PWA

DocPilot ships with a Progressive Web App manifest and service worker. In a compatible browser the interface can be installed like an app.

The PWA is an **installable interface to the local DocPilot service**. OCR, real-file access and indexing still require the local DocPilot backend to be running.

## Windows source/test run

Double-click:

```text
DocPilot.bat
```

The launcher can install Python when required, creates a private virtual environment, installs the full feature set and waits for the local service before opening the UI.

Manual equivalent:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[full]"
docpilot
```

Open:

```text
http://127.0.0.1:8765
```

## Architecture

```text
DocPilot Desktop / PWA
        │
        ▼
Local FastAPI service
        │
        ├── Smart Inbox / Batch / Watch Folder
        ├── OCR / scan cleanup / QR
        ├── Metadata / deadlines / actions
        ├── Review Queue
        ├── SQLite index / audit / undo
        ├── Local vector search / Local Q&A
        ├── Cases / Timeline / Duplicates / Diff
        ├── Sensitive-data detection / Redaction
        ├── Notifications
        ├── Calendar / Obsidian / Notion / backup
        └── Optional email / Notion / Google Calendar / MCP
```

## Feature status — v0.5.1

| Feature | Status |
|---|---|
| Real-file rename/move + verification | ✅ tested core |
| Undo history | ✅ tested core |
| PDF/text extraction | ✅ |
| Image OCR | ✅ with Tesseract |
| Scanned-PDF OCR | ✅ available |
| Auto rotate / deskew / cleanup | ✅ available |
| Deadline Radar | ✅ available |
| Review Queue | ✅ available |
| Smart Inbox / batch / watch folder | ✅ available |
| Exact + near duplicates | ✅ available |
| Receipt/invoice fields | ✅ available |
| Warranty / contract tracking | ✅ available |
| Cases / Timeline | ✅ available |
| Local vector search | ✅ tested local LSA |
| Local structured/extractive Q&A | ✅ available |
| Calendar / Obsidian / Notion exports | ✅ available |
| Full source-document backup | ✅ available |
| Sensitive-data detection | ✅ available |
| PDF raster/OCR redaction | 🧪 experimental; manual review required |
| Image/scanned-PDF OCR redaction | 🧪 experimental; manual review required |
| Rules / profiles / custom types | ✅ available |
| PWA | ✅ installable UI |
| Background Windows notifications | ✅ available |
| Gmail/Outlook IMAP import | 🧪 optional connector |
| Direct Notion sync | 🧪 optional connector |
| Direct Google Calendar sync | 🧪 optional OAuth connector |
| QR detection | ✅ with scan bundle |
| General barcode detection | 🧪 optional `pyzbar` |
| MCP server | 🧪 optional |

## Safety & privacy

DocPilot operates on real files. Test new builds on copies of non-critical documents first.

Automatically detected dates, amounts, PII and legal/financial fields may be incomplete or wrong. DocPilot is a document-management tool, not a substitute for checking the original source. Redacted copies must be visually reviewed before external sharing.

Cloud integrations are disabled unless configured by the user. Core processing remains local.

Security reports: please use GitHub Issues only for non-sensitive bugs. For security-sensitive reports, contact the repository owner privately. Do not attach private documents to public issues.

## Development

```bash
pip install -e ".[full,dev]"
pytest -q
```

Current test suite: **17 tests** covering core file operations, extraction, indexing, duplicates/diff helpers, Review Queue, local vector search, Local Q&A, scan preprocessing and full archive backup.

## Releases

Pushing the stable tag:

```text
v0.5.1
```

runs the Windows release workflow, tests the project, builds the desktop app and notifier, bundles OCR, creates Portable ZIP + Setup EXE, computes SHA-256 checksums and publishes the artifacts to GitHub Releases.

## Contributing

Issues and pull requests are welcome. For contributions: describe the problem, keep changes focused, add/update tests where practical, and verify `pytest -q` before opening a pull request.

## License

MIT — see `LICENSE`.
