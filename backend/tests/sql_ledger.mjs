import { PGlite } from '../../frontend/node_modules/@electric-sql/pglite/dist/index.js'
import { fileURLToPath } from 'node:url'
process.chdir(fileURLToPath(new URL('../..', import.meta.url)))
import { readFile, readdir } from 'node:fs/promises'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
const db = new PGlite()
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;')
const schema = (await readFile('backend/sql/schema.sql','utf8')).replace('create extension if not exists "pgcrypto";','')
await db.exec(schema)
for (const name of (await readdir('backend/sql/migrations')).filter(n=>n.endsWith('.sql')).sort()) await db.exec(await readFile('backend/sql/migrations/'+name,'utf8'))
await db.exec("insert into cash_accounts(name,currency,amount) values('duplicate','TWD',5),('duplicate','TWD',7)")
const migration=(await readdir('supabase/migrations')).find(name=>name.endsWith('_reliable_ledger.sql'))
const sql=await readFile('supabase/migrations/'+migration,'utf8')
await db.exec(sql)
const scalar = async sql=>(await db.query(sql)).rows[0]
assert.equal((await scalar("select amount::float8 as amount from cash_accounts where name='duplicate' and archived_at is null")).amount,12)
assert.equal((await scalar("select count(*)::integer as n from cash_accounts where name='duplicate' and archived_at is not null")).n,1)
await db.exec(sql) // repeatable and no second merge
assert.equal((await scalar("select amount::float8 as amount from cash_accounts where name='duplicate' and archived_at is null")).amount,12)
await db.exec("insert into cash_accounts(name,currency,amount) values('test-bank','TWD',100000); insert into manual_values(key,value) values('invested_美股',2000) on conflict(key) do update set value=2000;")
const revision = async ()=>(await scalar('select app_data_revision() as n')).n
const call = async (action,payload,id,op,effects,rev=null)=>(await db.query('select apply_app_operation($1,$2,$3,$4,$5,$6) as result',[action,payload,id,op,rev,effects])).rows[0].result
let request={movement_date:'2026-10-28',from_bucket:'test-bank',to_bucket:'美股',amount:32000,currency:'TWD',to_amount:1000,to_currency:'USD',note:'synthetic'}
let effects=[{kind:'cash',bucket:'test-bank',currency:'TWD',delta:'-32000'},{kind:'account',bucket:'美股',currency:'USD',delta:'1000'}]
const op='00000000-0000-4000-8000-000000000001'
const created=await call('movement.create',request,null,op,effects,await revision())
await call('movement.create',request,null,op,effects,0) // replay after revision changes
assert.equal((await scalar("select value::float8 as amount from manual_values where key='invested_美股'")).amount,3000)
assert.equal((await scalar("select amount::float8 as amount from cash_accounts where name='test-bank' and archived_at is null")).amount,68000)
await assert.rejects(call('movement.create',{...request,amount:32001},null,op,effects,await revision()))
request={movement_date:'2026-10-28',from_bucket:'美股',to_bucket:'test-bank',amount:500,currency:'USD',to_amount:16000,to_currency:'TWD'}
effects=[{kind:'account',bucket:'美股',currency:'USD',delta:'-500',available_cash:'1000'},{kind:'cash',bucket:'test-bank',currency:'TWD',delta:'16000'}]
const r=await revision()
await call('movement.create',request,null,'00000000-0000-4000-8000-000000000002',effects,r)
assert.equal((await scalar("select value::float8 as amount from manual_values where key='invested_美股'")).amount,2500)
assert.equal((await scalar("select amount::float8 as amount from cash_accounts where name='test-bank' and archived_at is null")).amount,84000)
await assert.rejects(call('movement.create',request,null,'00000000-0000-4000-8000-000000000003',effects,r)) // concurrent stale calculation
await assert.rejects(call('movement.create',request,null,'00000000-0000-4000-8000-000000000004',[...effects,{kind:'invalid',delta:1}],await revision()))
assert.equal((await scalar("select amount::float8 as amount from cash_accounts where name='test-bank' and archived_at is null")).amount,84000) // full rollback
await assert.rejects(call('movement.create',{...request,currency:'TWD'},null,'00000000-0000-4000-8000-000000000005',effects,await revision()))
await assert.rejects(call('movement.create',request,null,'00000000-0000-4000-8000-000000000006',[{...effects[0],available_cash:'100'}],await revision()))
// Audited calibration then editing/deleting older ledger entries must preserve confirmed cash.
const bank=await scalar("select id,updated_at from cash_accounts where name='test-bank' and archived_at is null")
await call('cash.update',{amount:90000,currency:'TWD',expected_updated_at:bank.updated_at.toISOString()},bank.id,'00000000-0000-4000-8000-000000000007',[])
assert.equal((await scalar('select count(*)::integer as n from balance_adjustments')).n,1)
const deleted=await call('movement.delete',{},created.id,'00000000-0000-4000-8000-000000000008',[{kind:'cash',bucket:'test-bank',currency:'TWD',delta:'32000'}],await revision())
assert.ok(deleted.balance_effect_note)
assert.equal((await scalar("select amount::float8 as amount from cash_accounts where name='test-bank' and archived_at is null")).amount,90000)
await assert.rejects(call('investment.bulk',{investments:[{id:'00000000-0000-4000-8000-000000000099',name:'deleted',cost:0,value:0,cash_amount:0,currency:'TWD'}]},null,'00000000-0000-4000-8000-000000000009',[]))
// Keyset pagination must not drop same-day/same-timestamp trades.
await db.exec("insert into trades(account,ticker,date,buy_qty,price,fee) select '美股','PAGE','2026-01-01',1,1,0 from generate_series(1,4)")
const page1=(await db.query("select list_app_trades_page('美股','PAGE',null,null,null,2) as rows")).rows[0].rows
assert.equal(page1.length,3)
const before={date:page1[1].date,created_at:page1[1].created_at,id:page1[1].id}
const page2=(await db.query("select list_app_trades_page('美股','PAGE',null,null,$1,2) as rows",[before])).rows[0].rows
assert.equal(page2.length,2);assert.equal(new Set([...page1.slice(0,2),...page2].map(row=>row.id)).size,4)
const rev=await revision()
assert.ok((await db.query('select publish_app_caches($1,$2) as stamp',[rev,{main:{ok:true}}])).rows[0].stamp)
assert.ok((await scalar("select read_app_cache('main') as payload")).payload)
await db.exec("update cash_accounts set amount=amount+1 where name='test-bank'")
assert.equal((await scalar("select read_app_cache('main') as payload")).payload,null)
assert.equal((await db.query('select publish_app_caches($1,$2) as stamp',[rev,{main:{ok:true}}])).rows[0].stamp,null)
await db.exec('set role anon')
await assert.rejects(db.query("select read_app_cache('main')"))
await db.exec('reset role')
console.log('PASS: complete schema + migrations, duplicate archive/idempotent upgrade, TWD → USD, USD → TWD, replay/conflict, rollback, currency/cash guard, revision CAS cache, anon denied')
await db.close()
// Build a genuinely empty new environment, without legacy personal seed balances.
execFileSync('python',['backend/scripts/database_setup.py'])
const clean = new PGlite()
await clean.exec('create role anon; create role authenticated; create role service_role bypassrls;')
await clean.exec((await readFile('tmp/database_setup.sql','utf8')).replace('create extension if not exists "pgcrypto";',''))
for (const table of ['trades','cash_accounts','manual_values','manual_investments','capital_movements']) {
  assert.equal((await clean.query(`select count(*)::int as n from ${table}`)).rows[0].n,0,`${table} must start empty`)
}
const verification = await clean.exec(await readFile('backend/sql/verify_reliable_ledger.sql','utf8'))
assert.equal(verification.length,1)
assert.equal(verification[0].rows[0].item,'overall')
assert.equal(verification[0].rows[0].detail,'50 checks; 0 failed')
assert.ok(verification[0].rows.every(row=>row.status==='PASS'))
await clean.exec('alter table public.cash_accounts disable row level security')
const failedVerification = (await clean.exec(await readFile('backend/sql/verify_reliable_ledger.sql','utf8')))[0].rows
assert.equal(failedVerification[0].status,'FAIL')
assert.ok(failedVerification.some(row=>row.kind==='table_permissions' && row.item==='cash_accounts' && row.status==='FAIL'))
await clean.close()
console.log('PASS: generated fresh-database setup creates all tables/RPCs without personal seed assets')
