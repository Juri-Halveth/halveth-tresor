# Security Policy

Thank you for helping keep Tresor and its users safe. This document explains which versions receive security fixes and how to report a vulnerability responsibly.

## Supported Versions

Security updates are provided for the latest 1.0.x release. Older patch releases are not maintained once a newer 1.0.x is published.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | Yes                |
| < 1.0   | No                 |

## Reporting a Vulnerability

Please report security issues privately. Do not open a public GitHub issue, pull request, or discussion for a suspected vulnerability, because that discloses the problem before a fix is available.

To report, open a private GitHub Security Advisory:

https://github.com/Juri-Halveth/halveth-tresor/security/advisories/new

This channel is private between you and the maintainer and is the preferred way to reach us for security matters. If you are unable to use GitHub Security Advisories, please contact the maintainer through the project's GitHub profile and ask for a private channel before sharing any details.

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