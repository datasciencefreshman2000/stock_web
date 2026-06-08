async function callBackend(env, path) {
  const apiBase = (env.API_BASE || '').replace(/\/$/, '')
  if (!apiBase) throw new Error('API_BASE is not configured.')
  if (!env.CRON_SECRET) throw new Error('CRON_SECRET is not configured.')

  const response = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    headers: {
      'X-Cron-Secret': env.CRON_SECRET,
    },
  })

  const body = await response.text()
  if (!response.ok) throw new Error(`${path} failed: ${response.status} ${body}`)
  return body
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(callBackend(env, '/jobs/snapshot'))
  },

  async fetch(request, env) {
    if (request.headers.get('X-Cron-Secret') !== env.CRON_SECRET) {
      return new Response('Forbidden', { status: 403 })
    }

    const url = new URL(request.url)
    const path = url.pathname === '/snapshot' ? '/jobs/snapshot' : '/jobs/refresh'

    try {
      const body = await callBackend(env, path)
      return new Response(body, { headers: { 'Content-Type': 'application/json' } })
    } catch (error) {
      return new Response(String(error?.message || error), { status: 500 })
    }
  },
}
