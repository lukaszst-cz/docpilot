# Security Policy

## Supported version

Security fixes are prepared for the current stable DocPilot release. Before reporting a problem, please check the latest release:

https://github.com/lukaszst-cz/docpilot/releases/latest

## Reporting a security issue

Please do not publish a security vulnerability as a public GitHub issue if it could expose user data, bypass file-safety checks, enable unintended file operations, or affect local integrations.

Send a private report to:

kontakt@zielona-marka.pl

Include, when possible:

- DocPilot version and Windows version;
- whether the issue affects Setup or Portable;
- the feature involved;
- clear reproduction steps using synthetic or redacted data;
- expected and actual behavior;
- relevant logs with personal data, document contents, tokens and credentials removed.

Do not send real confidential documents, passwords, API keys, OAuth tokens or private conversation archives.

## Security model

DocPilot is local-first. OCR, indexing, search and normal file operations are designed to run on the user's computer. Optional integrations can communicate with external services only when configured by the user.

Automated recognition can make mistakes. Important dates, amounts and extracted data should always be checked against the original document.

## Safe testing

Use the built-in safe demo or synthetic files when reproducing problems. Back up important archives before testing recovery, bulk operations or a new release.
