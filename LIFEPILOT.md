# LifePilot — foundation

LifePilot is an evolution path for DocPilot rather than a replacement.

## One-sentence product promise

> Wrzuć dokument. LifePilot powie Ci, co to jest, co trzeba zrobić, do kiedy i zachowa wszystko na później.

## Product layers

1. **DocPilot core** — local-first OCR, metadata, deadlines, cases, search, history and safe file operations.
2. **CoTeraz?** — turns the document state into one clear next action with priority and due date.
3. **ProofPack** — creates an evidence-oriented manifest with provenance and SHA-256 integrity data.
4. **CzyToŚciema?** — optional safety module for suspicious messages, links, screenshots and QR codes. It stays separately deployable and should be integrated only through a narrow contract.

## First thin slice

The first LifePilot slice intentionally does not change the SQLite schema.

For every indexed document it can derive:
- a single recommended next action;
- priority based on the nearest known deadline;
- a short explanation;
- a minimal ProofPack manifest with document identity, selected metadata and SHA-256.

The API exposes:

`GET /api/lifepilot/{document_id}`

The normal analysis response also includes a `lifepilot` object, so a future UI can show the recommendation immediately after upload.

## Safety rules

- no automatic destructive file action;
- no claim that OCR or inferred deadlines are authoritative;
- low-confidence extraction is routed to manual review first;
- ProofPack v1 is a manifest only; it does not silently copy or upload original file bytes;
- CzyToŚciema? remains isolated from private document contents unless the user explicitly sends selected content for checking.

## Next implementation steps

- add a dedicated LifePilot UI card after analysis;
- add a real ProofPack ZIP export with the original file, manifest, timeline and checksums;
- add reminders / calendar handoff from the next-action card;
- add a narrow local contract for optional CzyToŚciema? checks;
- run pilot tests on invoices, official letters, school documents, insurance correspondence and contracts.
