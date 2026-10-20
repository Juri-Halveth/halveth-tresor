# Security Policy

Thank you for helping keep Tresor and its users safe. This document explains which versions receive security fixes and how to report a vulnerability responsibly.

## Supported Versions

Security work targets the current 1.8.x source line (the inspected application version is 1.8.0). Use the newest published release from the project's Releases page. Historical 1.0.x versions are no longer the maintained line. This is a maintenance policy, not a guarantee of an independent audit or a response deadline.

| Version | Supported          |
| ------- | ------------------ |
| Latest 1.8.x | Current maintenance target |
| Older lines, including 1.0.x | No |

## Reporting a Vulnerability

Please report security issues privately. Do not open a public GitHub issue, pull request, or discussion for a suspected vulnerability, because that discloses the problem before a fix is available.

To report, open a private GitHub Security Advisory:

https://github.com/Juri-Halveth/halveth-tresor/security/advisories/new

If private reporting is available for your account, use that channel. Otherwise contact **security@halveth.de** to arrange a suitable private transfer before sharing sensitive details. Do not include real vaults or credentials.

### What to include

A good report helps us confirm and fix the issue quickly. Where possible, please include:

- A clear description of the vulnerability and its potential impact.
- The affected version (the release tag, or the version listed on the GitHub Releases page you downloaded from) and your operating system (Windows 10 or 11, x64).
- Step by step instructions to reproduce the issue.
- A minimal proof of concept, if you have one.
- Any relevant logs, screenshots, or configuration, with all real secrets removed.
- Your assessment of severity and any suggested remediation, if you have one.

Please do not include real passwords, PINs, recovery keys, or the contents of a real vault file in your report.

## Response Expectations

Tresor is maintained by a single developer, so timelines are best effort rather than guaranteed:

- Acknowledgement of your report: within 5 business days.
- Initial assessment and triage: within 10 business days.
- Fix or mitigation for confirmed, high severity issues: as soon as reasonably possible, prioritized ahead of other work.

We will keep you informed of progress and will let you know when a fix is released. With your permission, we are happy to credit you in the release notes and the advisory. Please allow a reasonable period for a fix to ship before any public disclosure, and let us coordinate the timing with you.

## Scope

This policy covers the disclosure process only. For the cryptographic design, the threat model, and the honest limits of what Tresor protects against (for example, it protects a stolen or copied vault file, but it does not protect against malware or a keylogger already running while the vault is unlocked), see:

[docs/security-model.md](docs/security-model.md)

Reports that describe behavior already documented as an accepted limitation in the security model may be closed as out of scope, but we still welcome them if you believe our assessment is wrong.
