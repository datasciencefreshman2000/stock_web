export function isEdgeStart(x, width, margin = 24) {
  return x < margin || x > width - margin
}
export function swipeIntent(dx, dy) {
  if (Math.abs(dy) >= 12 && Math.abs(dy) >= Math.abs(dx)) return 'scroll'
  if (Math.abs(dx) >= THRESHOLD_PX && Math.abs(dx) >= Math.abs(dy) * HORIZONTAL_RATIO) return 'navigate'
  return 'pending'
}
export const THRESHOLD_PX = 60
export const HORIZONTAL_RATIO = 1.5
