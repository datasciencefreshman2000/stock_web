# Cloudflare Cron Worker

This Worker keeps the existing Vercel FastAPI backend as the source of truth.

Schedule:

- `0 * * * *`: hourly run. The Worker writes a snapshot only at allowed full-hour Taipei times.
- `10,20,30,40,50 1 * * *`: Taipei 09:10 to 09:50 refresh-only runs.
- `30,40,50 13 * * *`: Taipei 21:30 to 21:50 refresh-only runs.
- `10,20,30 14 * * *`: Taipei 22:10 to 22:30 refresh-only runs.

Cloudflare cron uses UTC. The Worker converts the scheduled time to Taipei time
and skips autonomous runs from Taipei 04:00 to 08:00 and 14:30 to 20:30.
Non-full-hour runs call `/jobs/refresh`; full-hour runs call `/jobs/snapshot`.

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
