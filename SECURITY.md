# Security Policy

## Scope

KaiserClaim handles sensitive personal health data and insurance portal credentials. Security issues are taken seriously.

In scope:
- Credential or session data exposure
- Multi-tenant data isolation bypasses (`user_id` filtering)
- Injection vulnerabilities in the API or OCR pipeline
- Insecure storage of portal credentials or browser session cookies

Out of scope: issues in upstream dependencies (FastAPI, Playwright, Celery) — report those to the respective projects.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: **ladenhauf@protonmail.com** *(replace with your actual address before publishing)*

Please include:
- Description of the vulnerability and its impact
- Steps to reproduce or a proof-of-concept
- Affected version / commit SHA

You will receive an acknowledgement within 48 hours and a status update within 7 days.

## Responsible disclosure

We follow a 90-day coordinated disclosure window. We will credit reporters in the release notes unless you prefer to remain anonymous.

## Self-hosted deployments

If you run KaiserClaim yourself:

- **Never expose the API directly to the internet without authentication.** The current auth layer is a stub — add JWT middleware before going public.
- Store `MERKUR_PASSWORD`, `SECRET_KEY`, and all other credentials in a secret manager (k3s Secret, Vault, etc.) — not in `.env` files on shared systems.
- The `STORAGE_ROOT` directory contains invoice PDFs with medical and financial data. Restrict filesystem permissions accordingly.
- The ÖGK browser session directory (`STORAGE_ROOT/.oegk_browser_session`) contains live authentication cookies. Treat it with the same care as a password file.
