import test from 'node:test'
import assert from 'node:assert/strict'
import { isEdgeStart, swipeIntent } from '../src/utils/swipeIntent.js'

test('leave both phone screen edges to browser/system back gestures',()=>{
  assert.equal(isEdgeStart(12,390),true)
  assert.equal(isEdgeStart(380,390),true)
  assert.equal(isEdgeStart(100,390),false)
})
test('vertical scroll intent locks before it can become a page swipe',()=>{
  assert.equal(swipeIntent(4,18),'scroll')
  assert.equal(swipeIntent(5,6),'pending')
  assert.equal(swipeIntent(70,10),'navigate')
  assert.equal(swipeIntent(40,10),'pending')
})
