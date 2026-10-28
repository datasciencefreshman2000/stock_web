export function taipeiDate(date = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date)
}
export function currentMonth() { return taipeiDate().slice(0, 7) }
