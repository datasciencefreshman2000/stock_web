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

const TAIPEI_OFFSET_MS = 8 * 60 * 60 * 1000

function getTaipeiTimeParts(scheduledTime) {
  const scheduledAt = typeof scheduledTime === 'number' ? scheduledTime : Date.now()
  const taipeiTime = new Date(scheduledAt + TAIPEI_OFFSET_MS)
  return {
    hour: taipeiTime.getUTCHours(),
    minute: taipeiTime.getUTCMinutes(),
  }
}

function minutesFromMidnight(hour, minute) {
  return hour * 60 + minute
}

function isBetweenInclusive(time, startHour, startMinute, endHour, endMinute) {
  const value = minutesFromMidnight(time.hour, time.minute)
  const start = minutesFromMidnight(startHour, startMinute)
  const end = minutesFromMidnight(endHour, endMinute)
  return value >= start && value <= end
}

function shouldSkipScheduledRun(time) {
  return (
    isBetweenInclusive(time, 4, 0, 8, 0) ||
    isBetweenInclusive(time, 14, 30, 20, 30)
  )
}

function getScheduledJobPath(scheduledTime) {
  const taipeiTime = getTaipeiTimeParts(scheduledTime)
  if (shouldSkipScheduledRun(taipeiTime)) return null
  return taipeiTime.minute === 0 ? '/jobs/snapshot' : '/jobs/refresh'
}

export default {
  async scheduled(event, env, ctx) {
    const path = getScheduledJobPath(event.scheduledTime)
    if (!path) return
    ctx.waitUntil(callBackend(env, path))
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
