# Deploying SkillSwap AI

Everything needed to put the app online, on any host. Nothing in this guide depends
on a specific provider — the app runs anywhere that can run Python and serve static
files. Every integration below is **optional and degrades gracefully**: with no env
vars at all, the app still boots (sqlite-style dev DB excepted — Postgres is the one
hard requirement in production).

## The pieces

| Piece | What it is | Hard requirement? |
|---|---|---|
| Backend | FastAPI app in `backend/` | Yes |
| Database | PostgreSQL | Yes (production) |
| Frontend | Static build of `frontend/` (Vite SPA) | Yes |
| Redis | Caching + distributed locks | No — app runs without it |
| Groq | AI features (roadmaps, coach, interview…) | No — AI features show a friendly fallback |
| Resend/SMTP | Verification + password-reset email | No — users self-verify inline |
| Stripe | Real payments for Pro/Elite/token packs | No — upgrades use the instant stub |
| OAuth | "Continue with Google/GitHub/…" buttons | No — unset providers don't appear |

## Hosting options

- **Paid Render (~$7/mo)** — simplest: one Web Service (backend), one Static Site
  (frontend), managed Postgres. Note: **Render's free tier blocks outbound SMTP**,
  so use Resend (HTTPS) for email there.
- **A VPS / friend's server / Oracle free VM** — run both pieces yourself (commands
  below), Postgres locally or on **Neon** (free managed Postgres: neon.tech — copy
  its connection string into `DATABASE_URL`). A real VM doesn't block SMTP.
- **Free host with spin-down** (Render free, etc.) — works, but the first request
  after idle takes ~30s, and SMTP is blocked (use Resend).

## Backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head          # creates/updates all tables (needs DATABASE_URL)
uvicorn main:app --host 0.0.0.0 --port 8000
```

On Render: Build command `pip install -r requirements.txt`, Start command
`alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`,
root directory `backend`.

## Frontend

```bash
cd frontend
npm install
npm run build                 # outputs frontend/dist
```

Serve `frontend/dist` as a static site with SPA fallback (all routes →
`index.html`). If the frontend and backend live on **different origins**, set
`VITE_API_BASE_URL` to the backend's URL **at build time** (it's baked into the
bundle), and set `CORS_ORIGINS` on the backend to the frontend's URL.

## Environment variables (backend)

Names are case-insensitive; a local `.env` file works in development
(see `backend/.env.example`). **Never commit real values.**

### Core (set these first)

| Var | Value |
|---|---|
| `DATABASE_URL` | Postgres connection string. `postgres://`/`postgresql://` prefixes are auto-normalized to the async driver. |
| `APP_SECRET_KEY` | Long random string (e.g. `openssl rand -hex 32`). Signs auth tokens — changing it logs everyone out. |
| `APP_ENV` | `production` (hides dev-only token shortcuts). |
| `CORS_ORIGINS` | Frontend URL(s), comma-separated — e.g. `https://app.example.com`. Avoid `*` in production. |
| `FRONTEND_URL` | Frontend base URL — used to build links inside emails and OAuth redirects. |

### AI

| Var | Value |
|---|---|
| `GROQ_API_KEY` | From console.groq.com → API Keys (free tier exists). |
| `GROQ_MODEL` | Optional; defaults to `llama-3.3-70b-versatile`. |

### Redis (optional)

| Var | Value |
|---|---|
| `REDIS_URL` | e.g. `redis://host:6379`. Unset/down → caching and locks are skipped. |

### Email — pick ONE path

**Resend (recommended — works on hosts that block SMTP, free 100 emails/day):**

| Var | Value |
|---|---|
| `RESEND_API_KEY` | From resend.com → API Keys (`re_…`). |
| `EMAIL_FROM` | `SkillSwap AI <onboarding@resend.dev>` until you verify your own domain in Resend, then your own address. |

**SMTP (any provider; Gmail needs an App Password):**

| Var | Value |
|---|---|
| `SMTP_HOST` | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | `587` (STARTTLS) or `465` (set `SMTP_SSL=true`, `SMTP_STARTTLS=false`) |
| `SMTP_USER` / `SMTP_PASSWORD` | Account + App Password |
| `EMAIL_FROM` | `SkillSwap AI <you@example.com>` |

With neither set, verification falls back to instant inline self-verify — the app
tells users plainly that this server doesn't send email.

### Stripe (real payments)

| Var | Value |
|---|---|
| `STRIPE_SECRET_KEY` | dashboard.stripe.com → Developers → API keys. Use `sk_test_…` first; swap to `sk_live_…` when ready. |
| `STRIPE_WEBHOOK_SECRET` | The `whsec_…` for your webhook endpoint. |

Webhook setup: Dashboard → Developers → Webhooks → **Add endpoint** (sometimes
labeled "Add destination") → URL `https://<backend>/billing/webhook` → select events
`checkout.session.completed` and `customer.subscription.deleted` → copy the signing
secret into `STRIPE_WEBHOOK_SECRET`. Without the key, Plans still works via the
instant-upgrade stub (no money moves).

### OAuth sign-in (each provider is independent)

Set a pair to make its button appear. **Redirect URI for every provider:**
`<FRONTEND_URL>/oauth/callback`.

| Provider | Vars | Where to create the app |
|---|---|---|
| Google | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | console.cloud.google.com → APIs & Services → Credentials → OAuth client ID (Web) |
| GitHub | `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | github.com/settings/developers → OAuth Apps |
| LinkedIn | `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | developer.linkedin.com (add "Sign In with LinkedIn using OpenID Connect") |
| Discord | `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | discord.com/developers/applications |
| Microsoft | `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` | portal.azure.com → App registrations |

### Extras (all optional)

| Var | Purpose |
|---|---|
| `ADMIN_EMAILS` | Comma-separated emails granted the admin/moderation panel. |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Web push notifications (`npx web-push generate-vapid-keys`). |
| `CRON_SECRET` | Shared secret for an external scheduler to hit the daily-reminder job (`X-Cron-Secret` header). |
| `SENTRY_DSN` | Error monitoring via Sentry. |
| `LOG_JSON` | `true` in production for log aggregators. |

## Checklist for a fresh deploy

1. Create the Postgres database; set `DATABASE_URL`.
2. Set `APP_SECRET_KEY`, `APP_ENV=production`, `CORS_ORIGINS`, `FRONTEND_URL`.
3. Deploy the backend (migrations run via `alembic upgrade head`).
4. Build the frontend with `VITE_API_BASE_URL` pointing at the backend; deploy `dist/`.
5. Add `GROQ_API_KEY` for AI features.
6. Add `RESEND_API_KEY` + `EMAIL_FROM` for real verification emails.
7. Add Stripe keys + webhook when you're ready to charge.
8. Add OAuth provider pairs for social sign-in.
9. Sign in, open Settings → verify email, and buy a test plan with Stripe test
   card `4242 4242 4242 4242` to confirm the loop.
