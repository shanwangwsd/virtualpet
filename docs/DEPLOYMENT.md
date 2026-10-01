# Deployment Guide

Configuration is provided. No hosting account, paid resource, DNS change, or public release was created automatically.

## Prerequisites

- A Linux host with Docker Compose.
- A domain you control that points to the host.
- Ports 80/443 available; the database must not be public.
- Strong random SECRET_KEY and DB_PASSWORD in `.env`, plus `DOMAIN=pet.example.com` and `ALLOWED_HOSTS=pet.example.com`.
- The image is pinned to pgvector 0.8.2/PostgreSQL 18. Verify it can be pulled. Initial development used local PostgreSQL because Docker Desktop did not start.

## Deploy

```sh
python3 scripts/create_env.py
# Edit .env with your domain and private configuration.
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up --build -d
docker compose logs --tail=100 api jobs
```

Caddy manages HTTPS. The API's host port remains bound to 127.0.0.1, and Caddy reaches it over the container network. Only the trusted proxy should set forwarded-proto; do not expose the API directly as another public endpoint.

Check `https://your-domain/healthz/`, then run `scripts/smoke_api.py --url https://your-domain` to test with a temporary account.

## Before a long-lived public deployment

- The initial migration must be able to create the vector extension, or an administrator must install it first.
- The example uses one database role for convenience. Separate migration and least-privilege runtime roles for production and verify their permissions.
- DRF's in-memory rate limits are per process, not a global multi-worker quota. Add shared or proxy-level limits and set a provider-side spending limit.
- Test the actual model's structured-output support and embedding dimensions.
- Validate real Apple signing, HealthKit, APNs, background behavior, and battery use.
- Match privacy disclosures to the actual model provider, storage region, and retention policy.
- Clean expired tokens periodically with `python manage.py flushexpiredtokens`.

## APNs keys

Store the `.p8` key privately on the server, outside the repository. Mount it read-only into api/jobs with an override and use its container path in APNS_KEY_PATH. Never bake the key into an image.

## Backups and restore drills

```sh
# The backup contains private data. Store it securely.
docker compose exec -T db pg_dump -U habitpet -Fc habitpet > habitpet.backup
```

Restore into a new empty database first. Check accounts, inventory, memory counts, and vector retrieval. Use the appropriate role after production role separation.

Back up before upgrades. Check migration reversibility before rollback: reverting an image does not automatically undo every schema change.

## Observability

Monitor health checks, HTTP errors/latency, AI fallback rate, model token usage, APNs status codes, and background job failures. Logs avoid secrets and full health/chat content. Reconcile costs against the provider bill; no fabricated cost estimates are emitted.
