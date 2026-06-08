# Cloudflare Cron Worker

This Worker keeps the existing Vercel FastAPI backend as the source of truth.

Schedules:

- `0 * * * *`: refresh prices and summary cache every hour.
- `10 16 * * *`: write a daily asset snapshot at 00:10 Asia/Taipei. Cloudflare cron uses UTC, so 16:10 UTC is 00:10 in Taiwan.

Worker variables/secrets:

```text
API_BASE=https://stock-web-gamma.vercel.app/api
CRON_SECRET=<same value as Vercel CRON_SECRET>
```

Backend endpoints called by the Worker:

```text
POST /api/jobs/refresh
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
