# Vanguard Gym OS — Deployment Safety Notes

This package has received targeted safety and deployment edits. It has **not** been proven fully functional by a complete integration test.

## Changes in this package

- Production startup now requires a unique `SECRET_KEY` of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"` and set it in the hosting provider's private environment settings. Do not commit it.
- Database schema initialization errors stop application startup instead of being silently ignored.
- If a PostgreSQL URL is configured but the connection fails in production, the app refuses to silently switch to SQLite. This prevents the app from appearing to work while writing to a temporary/different database.
- State-changing POST/PUT/PATCH/DELETE requests require a session CSRF token. HTML POST forms include it, and scanner API calls send it in a header. Automated test mode skips CSRF enforcement.
- Owner first-time setup and password change require passwords of at least 12 characters.
- The owner-preparation script now requires explicit `WIPE ALL DATA` confirmation, prompts for a password without echoing it, and no longer prints the password. It is destructive: do not run it against a database containing records you need.
- QR scanner output escapes server-provided text before rendering it as HTML.
- Tests use a separate SQLite test database by default.

## Production deployment requirements

1. Use a persistent PostgreSQL database for a hosted service whose local disk is ephemeral. Configure `DATABASE_URL` privately in the host dashboard.
2. Confirm the database provider's current free-tier, inactivity, backup, and retention terms. Do not assume a free database is permanent or backed up.
3. Set `APP_ENV=production`, `FLASK_ENV=production`, `SECRET_KEY`, `DATABASE_URL`, and `GYM_TIMEZONE=Asia/Karachi` in hosting settings as appropriate.
4. Do not add `.env`, database dumps, real customer records, or credentials to GitHub. `.gitignore` excludes `.env` and `*.db` files.
5. After deployment, create the owner through the one-time setup wizard. Use a unique password and change it if it has been shared.
6. Test owner/staff/member permissions, member registration, attendance, duplicate check-in, payment records, database persistence after restart, and backup/restore before handing the portal over.

## Verification performed here

- Python source files compile successfully with `compileall`.
- All 18 HTML POST forms found in templates contain a CSRF hidden input.
- Full pytest execution could not be completed in this environment because Flask is not installed in the available Python runtime. Do not treat the test suite as passing until it is run in an environment with the requirements installed.
