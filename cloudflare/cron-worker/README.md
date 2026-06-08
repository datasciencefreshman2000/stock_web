# Cloudflare Cron Worker

This Worker keeps the existing Vercel FastAPI backend as the source of truth.

Schedule:

- `0 * * * *`: refresh prices, update summary cache, and write one hourly asset snapshot.

Worker variables/secrets:

```text
API_BASE=https://stock-web-gamma.vercel.app/api
CRON_SECRET=<same value as Vercel CRON_SECRET>
```

Backend endpoints called by the Worker:

```text
POST /api/jobs/snapshot
```

Both endpoints require:

```text
X-Cron-Secret: <CRON_SECRET>
```

Manual test URLs after deployment:

```text
https://<worker-name>.<your-subdomain>.workers.dev/refresh
https://<worker-name>.<your-subdomain>.workers.dev/snapshot
```

Manual requests must include:

```text
X-Cron-Secret: <CRON_SECRET>
```
