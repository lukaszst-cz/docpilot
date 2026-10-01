# Contributing to DocPilot

Thanks for testing or improving DocPilot.

## Before opening a change

1. Check existing issues and the current README.
2. Reproduce the problem on the current stable release or current `main`.
3. Use synthetic, anonymized or redacted documents only.
4. Keep changes focused on one problem.

## Development

DocPilot uses Python, SQLite and a local web interface. Windows packaging is covered by the repository workflows and release scripts.

Run the automated test suite before submitting a change:

```bash
python -m unittest discover -v
```

For a focused change, run the relevant test module as well.

## Bug reports

A useful bug report includes:

- DocPilot version;
- Windows version;
- Setup or Portable;
- steps to reproduce;
- expected result;
- actual result;
- whether the issue can be reproduced with the safe demo;
- sanitized logs if relevant.

Use the repository bug-report template:

https://github.com/lukaszst-cz/docpilot/issues/new?template=bug_report.yml

## Feature requests

Describe the user problem first, then the proposed behavior. Prefer changes that keep the local-first model, explicit user approval before file changes, and reversible operations where practical.

https://github.com/lukaszst-cz/docpilot/issues/new?template=feature_request.yml

## Privacy

Never commit real invoices, contracts, scans, e-mail exports, credentials, tokens or other private user data. Test fixtures should contain fictional data only.

## Pull requests

Keep commits small and descriptive. A pull request should explain what changed, why it changed, how it was tested and any compatibility or migration impact.
