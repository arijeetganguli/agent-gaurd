# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Agent Guard, please report it responsibly.

**Do NOT open a public issue.**

Instead, email **cooldevil.ari@gmail.com** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You will receive an acknowledgment within 48 hours. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Security Scope

Agent Guard is a security governance tool. The following areas are in scope:

- **Policy bypass** — ways to circumvent security policy enforcement
- **Execution engine escape** — breaking out of the sandbox or approval gates
- **Prompt injection** — injection patterns not caught by PI-001/PI-002/PI-003
- **Secret exposure** — cases where secrets leak through generated instruction files
- **Audit log tampering** — ways to modify or delete audit entries

## Out of Scope

- Vulnerabilities in upstream dependencies (report to the respective project)
- Issues requiring physical access to the machine
- Social engineering attacks
