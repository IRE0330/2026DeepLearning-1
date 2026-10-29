// Run the exact browser lookup against Python's generated expected results.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const assert=require('node:assert/strict');
const folder=process.argv[2]||'.local-run/distance-ui-test';
const fixture=JSON.parse(fs.readFileSync(path.join(folder,'browser-case.json'),'utf8'));
const context=vm.createContext({});
new vm.Script(fs.readFileSync(path.join(folder,'browser-distance.js'),'utf8')).runInContext(context);
function lookup(rows,t){context.inputRows=rows;context.inputTime=t;return vm.runInContext('distanceAt(inputRows,inputTime)',context);}
for(const query of [...fixture.queries,...fixture.queries.toReversed()]){
  const actual=lookup(fixture.rows,query.t),expected=query.expected;
  assert.equal(actual.status,expected.status,'status at '+query.t);
  assert.equal(actual.wait,expected.wait,'wait at '+query.t);
  assert.equal(!!actual.held,!!expected.held,'held at '+query.t);
  assert.equal(actual.stability,expected.stability,'stability at '+query.t);
  if(actual.held)assert.ok(query.t-actual.last_valid_time_s<=3+1e-9);
}
const paused=JSON.stringify(lookup(fixture.rows,5));
for(let i=0;i<10;i++)assert.equal(JSON.stringify(lookup(fixture.rows,5)),paused);
assert.equal(lookup([],50).status,'측정 불가');
assert.equal(lookup(fixture.rows,0).status,'측정 불가');
assert.equal(lookup(fixture.rows,11.001).status,'측정 불가');
console.log('PASS Python/browser parity:',fixture.queries.length,'timestamps forward/backward, exact expiry, pause, reset and new run');
