# delivery.mumtaz.digital

C2P Agency OS: the AI delivery console. FastAPI back end and a single-file web console.

| | |
|---|---|
| **Status** | **Production** |
| **Code** | [`c2p-delivery-system/`](../../c2p-delivery-system/) — `delivery_api/` (API), `console/` (web console), `deploy/` (scripts), `docs/` |
| **Database** | SQLite files beside the code on the server: `delivery.db`, `control.db`, one file per tenant |
| **Service** | uvicorn on port 8800 (loopback), behind nginx |
| **Deploy** | On the server: `bash /opt/mumtaz/c2p-delivery-system/deploy/update.sh` |
| **Connects to** | An Odoo database (stored, encrypted connection), GitHub (stored token), an LLM provider |

**Not moved.** The server deploys from this exact path, and untracked files (`.env`, the SQLite stores) sit inside it. Moving it needs a short server-side step first.

## Landing page

[`landing/`](landing/) is a one-page marketing page whose buttons all lead to this console (was `website/index.html` and `website/assets/` until 22 Nov 2026). It is not served: nginx's root for this hostname is the console folder. A CI job only checks that its three files exist.

## What the server check of 22 Nov 2026 showed

- nginx serves this hostname from `/opt/mumtaz/c2p-delivery-system/web`, as documented.
- **That checkout is on branch `claude/resume-help-95ne9v`, not `main`.** `deploy/update.sh` runs `git pull --ff-only origin main`; on a branch that has diverged from `main` that command refuses to run. So a merge to `main` does not by itself reach this console. Which commit the console is actually on has not been checked yet.

## Open points

- Authentication is switched on by a setting and fails open if the setting is mistyped (audit C2P-01). Confirm which mode production runs in.
- Stored credentials can be redirected to another host by anyone with API access (C2P-02, -03).
- No backup of the SQLite stores or the encryption key (C2P-14).
