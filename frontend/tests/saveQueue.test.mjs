import test from 'node:test'
import assert from 'node:assert/strict'
import { createSaveQueue } from '../src/lib/saveQueue.js'
import { taipeiDate } from '../src/utils/dates.js'
const tick = () => new Promise(resolve => setTimeout(resolve, 10))
function storage() { const map = new Map(); return { getItem: key => map.get(key), setItem: (key,value) => map.set(key,value) } }

test('failed saves preserve operation ID; duplicate retry clicks send once', async () => {
  const calls=[]; let fail=true
  const queue=createSaveQueue({storage:storage(),send:async (kind,payload)=>{ calls.push(payload.operation_id); if(fail) throw Error('offline') }})
  const id=queue.enqueue('movement',{amount:100},'test')
  await tick(); assert.equal(queue.getSnapshot()[0].state,'failed')
  fail=false;queue.retry(id);queue.retry(id);await tick()
  assert.deepEqual(calls,[id,id]);assert.deepEqual(queue.getSnapshot(),[])
})
test('reload restores uncertain in-flight jobs and retry uses original ID', async () => {
  const local=storage()
  const first=createSaveQueue({storage:local,send:()=>new Promise(()=>{})})
  const id=first.enqueue('movement',{amount:100},'test')
  const calls=[];const restored=createSaveQueue({storage:local,send:async(_,payload)=>calls.push(payload.operation_id)})
  assert.equal(restored.getSnapshot()[0].state,'failed')
  restored.retry(id);await tick();assert.deepEqual(calls,[id])
})
test('writes are serialized and a post-commit read error cannot requeue money', async () => {
  let active=0,max=0
  const queue=createSaveQueue({storage:storage(),send:async()=>{active++;max=Math.max(max,active);await tick();active--},onSaved:()=>{throw Error('read unavailable')}})
  queue.enqueue('movement',{amount:10});queue.enqueue('movement',{amount:20})
  await tick();await tick();await tick()
  assert.equal(max,1);assert.equal(queue.getSnapshot().length,0)
})
test('Taipei midnight is today even while UTC is still yesterday',()=>{
  assert.equal(taipeiDate(new Date('2026-10-27T16:30:00Z')),'2026-10-28')
})
