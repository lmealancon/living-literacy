# Security policy — draft

## Current status

Living Literacy is a synthetic-data prototype. It has not been approved for deployment with real students, guardians, educators, or institutional records. Synthetic tokens, simulated guardian/consent fixtures and reviewer labels are not production identity or authorization. Do not expose the local server to a public network. Do not commit credentials, real student data, logs containing personal information, or database files.

## Reporting a vulnerability

**A private security reporting channel has not yet been established.** Before publishing this repository, the owner must designate a monitored private channel, an accountable maintainer, and an initial response and disclosure process. A public repository must not imply that this draft offers a staffed reporting service.

Do not report exploit details, credentials, private records, or sensitive data in a public issue. If a private, owner-approved contact is available to you, report there without including real student data or credentials. If no private contact exists, do not disclose the details publicly; ask the project owner for a secure reporting route. Do not test on systems or accounts without authorization.

A useful private report includes affected version, a minimal synthetic reproduction, impact, and any safe mitigation. Do not access, copy, or share other users' data to demonstrate a problem.

## Release and incident readiness

Supported versions, coordinated disclosure timelines, incident contacts, and a security maintenance schedule remain undecided. Production readiness requires the controls in `specs/PRIVACY_SECURITY.md` and `specs/RELEASE_GATES.md`, including independently verified access isolation, consent, incident response, retention, backups and restoration. No security certification or legal compliance is claimed.
