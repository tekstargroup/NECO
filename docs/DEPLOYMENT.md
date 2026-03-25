# NECO deployment — auth and environment

## JWT policy (enforced at startup)

Any deploy where `ENVIRONMENT` is **not** one of `development`, `dev`, or `local` **must** have verified Clerk JWTs configured. The app will not start otherwise.

This includes **staging**, **production**, **demo**, and shared QA hosts. Do not rely on naming conventions alone—the check is enforced in `backend/app/core/config.py` (`Settings.model_post_init`).

### Required variables (non-local deploys)

| Variable | Required | Notes |
|----------|----------|--------|
| `CLERK_JWT_VERIFY` | Yes | `true` |
| `CLERK_JWKS_URL` | Yes | Clerk JWKS URL, e.g. `https://<instance>.clerk.accounts.dev/.well-known/jwks.json` |
| `CLERK_JWT_ISSUER` | Strongly recommended | Issuer URL for `iss` validation |
| `CLERK_JWT_AUDIENCE` | When needed | Set if tokens include `aud` and you must restrict to one Clerk application |

### Local development

Set `ENVIRONMENT=development` (or `dev` / `local`). You may run with `CLERK_JWT_VERIFY=false` for local-only work; a warning is logged.

### CI / automated tests

Use `ENVIRONMENT=development` (or provide `CLERK_JWT_VERIFY=true` and a valid `CLERK_JWKS_URL`) so imports of `app.core.config` do not fail during test collection.

See also `backend/.env.example` for a template of core variables.
