// Run the exact inline browser functions against model-free Python fixtures.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const folder=process.argv[2]||'.local-run/cctv-overflow-tests';
const fixture=JSON.parse(fs.readFileSync(folder+'/cases.json','utf8'));
const context=vm.createContext({});
new vm.Script(fs.readFileSync(folder+'/distance.js','utf8')).runInContext(context);
const evaluate=(code,values={})=>{Object.assign(context,values);return vm.runInContext(code,context);};
for(const query of [...fixture.queries,...fixture.queries.toReversed()]){
  const actual=evaluate('distanceAt(rows,t)',{rows:fixture.rows,t:query.t});
  for(const key of ['status','wait','stability','last_valid_time_s'])assert.equal(actual[key],query.expected[key],key+' at '+query.t);
  assert.equal(!!actual.held,!!query.expected.held);
  assert.equal(!!actual.overflow,!!query.expected.overflow);
}
assert.equal(evaluate('distanceAt([],100).wait'),'대기정보 확인 중');
assert.equal(evaluate('distanceAt(rows,100,{ended:true}).stability',{rows:fixture.rows}),'재생 종료');
const overflow=evaluate('distanceAt(rows,5)',{rows:fixture.rows});
assert.equal(overflow.wait,'15분 이상');
assert.equal(evaluate('totalWaitLabel(d,120)',{d:overflow}),'17분 이상');
assert.equal(evaluate('distanceRank(d)',{d:overflow}),Infinity);
const failed=evaluate('distanceAt(rows,5,{failed:true})',{rows:fixture.rows});
assert.equal(failed.stability,'갱신 지연');assert.equal(failed.last_valid_time_s,5);
const vals={north:{distance:{reached_m:0}},south:{distance:{reached_m:5}},east:{distance:overflow}};
assert.equal(evaluate('recommendDistance("east",vals,{walk:{}})',{vals}),null);
console.log('PASS overflow Python/browser parity, retained values, initial missing, seek/reset, EOF, failure, lower bounds and conservative ranking');
