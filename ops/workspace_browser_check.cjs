/* Optional browser verification. Uses isolated Chrome via Playwright; no live model.
 * NODE_PATH=<directory containing playwright> node ops/workspace_browser_check.cjs <new-private-root>
 * Never point this at a historical store. Artifacts and simulated UI states are labeled.
 */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const root = path.resolve(process.argv[2] || '');
if (!process.argv[2] || fs.existsSync(root)) throw Error('A new private output directory is required');
fs.mkdirSync(root, { mode: 0o700, recursive: true });
const checks = [], errors = [], failures = [];
let child, browser, origin;
async function launch(port = 0) {
  child = spawn(path.resolve('.venv/bin/python'), ['-m','secops_triage.workspace','--root',path.join(root,'workspace'),'--port',String(port)], { stdio:['ignore','pipe','pipe'] });
  return await new Promise((resolve,reject) => {
    const timer=setTimeout(()=>reject(Error('server startup timeout')),15000);
    child.once('exit', code=>{clearTimeout(timer);reject(Error(`server exited ${code}`));});
    child.stderr.on('data',()=>{}); // Do not export raw server exceptions.
    child.stdout.on('data', data=>{const match=String(data).match(/http:\/\/127\.0\.0\.1:\d+/);if(match){clearTimeout(timer);resolve(match[0]);}});
  });
}
async function stop() { if(child && child.exitCode===null){const ended=new Promise(r=>child.once('exit',r));child.kill('SIGINT');await ended;} }
async function ready(page) { await page.waitForFunction(()=>!document.querySelector('#packet-content').hidden, {timeout:20000}); }
async function choose(page, index) { await page.locator('#case-list button').nth(index-1).click(); }
async function scripted(page,index) { await choose(page,index);await page.locator('#start').click();await ready(page); }
async function fillHandoff(page) {
  await page.locator('#actor').fill('Automated browser verification, not human acceptance');
  await page.locator('#reason').fill('Synthetic verification: preserve uncertainty and retrieve missing context.');
  await page.locator('#missing').fill('Credential submission and source trust remain unproven.');
  await page.locator('#next-action').fill('Obtain an authorized audit export before a final decision.');
}
(async()=>{
try {
  origin=await launch();
  browser=await chromium.launch({headless:true,channel:'chrome'});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));
  await context.route('**/*',route=>route.request().url().startsWith(origin+'/') ? route.continue() : (errors.push('unexpected external browser request'),route.abort()));
  const page=await context.newPage();await page.goto(origin);await page.locator('#case-list button').nth(8).waitFor();
  assert.equal(await page.locator('#case-list button').count(),9);
  await page.keyboard.press('Tab');assert.equal(await page.locator(':focus').innerText(),'Skip to investigation');
  await page.keyboard.press('Enter');assert.equal(await page.locator(':focus').getAttribute('id'),'investigation');
  checks.push('nine incident queue and keyboard skip link');
  await scripted(page,4);
  assert.equal(await page.locator('#trace > li').count(),9);
  assert.match(await page.locator('#run-view').innerText(),/Saved execution/);
  assert.match(await page.locator('#recommendation-title').innerText(),/Escalate/i);
  assert.equal(await page.locator('#messages > *').count(),2);
  const traceText=await page.locator('#trace').innerText();
  for(const tool of ['inspect_incident','lookup_entity','query_activity','find_related_cases'])assert.ok(traceText.includes(tool));
  checks.push('real scripted Strands hero: four tools, nine reads, two-message comparison, saved execution label');
  const citation=page.locator('#trace .citation').first();await citation.click();
  assert.equal(await page.locator(':focus').getAttribute('id'),'source-heading');
  await page.keyboard.press('Escape');assert.equal(await page.locator('#source-detail').isHidden(),true);
  assert.equal(await page.locator(':focus').getAttribute('class'),'citation');
  checks.push('evidence detail, keyboard focus and Escape return');
  await fillHandoff(page);await page.reload();await ready(page);assert.match(await page.locator('#reason').inputValue(),/Synthetic verification/);
  await page.locator('#save').click();await page.locator('#copy-note').waitFor();
  const heroId=await page.locator('#history').inputValue();
  await page.reload();await ready(page);assert.match(await page.locator('#saved-records').innerText(),/Automated browser verification/);
  const port=Number(new URL(origin).port);await stop();await launch(port);await page.reload();await ready(page);
  assert.equal(await page.locator('#history').inputValue(),heroId);
  assert.equal(await page.locator('#trace > li').count(),9);
  assert.match(await page.locator('#saved-records').innerText(),/Automated browser verification/);
  checks.push('draft reload, durable unresolved handoff, server restart without redispatch');
  await page.screenshot({path:path.join(root,'hero-desktop.png'),fullPage:true});
  for(const width of [819,375]){
    await page.setViewportSize({width,height:1000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`overflow at ${width}`);
    await page.screenshot({path:path.join(root,`hero-${width}.png`),fullPage:true});
  }
  await page.setViewportSize({width:720,height:500}); // Equivalent layout viewport to 1440x1000 at 200% zoom.
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  checks.push('responsive 819px/375px and 200-percent-equivalent layout viewport, no horizontal overflow');
  await page.setViewportSize({width:1440,height:1000});
  // An actual newer scripted revision in a second tab must lock the old packet.
  await page.locator('#reason').fill('Stale draft preserved for exact old packet.');
  const other=await context.newPage();await other.goto(origin);await ready(other);
  await other.locator('#new-revision').click();await other.locator('#confirm-revision').click();await ready(other);
  await page.waitForFunction(()=>!document.querySelector('#stale').hidden);
  assert.equal(await page.locator('#save').isDisabled(),true);
  assert.equal(await page.locator('#reason').inputValue(),'Stale draft preserved for exact old packet.');
  await page.locator('#open-latest').click();await ready(page);
  assert.notEqual(await page.locator('#history').inputValue(),heroId);
  checks.push('explicit new revision, stale decision blocked and old draft retained');
  // Duplicate API start returns saved revision without creating another SDK session.
  const duplicate=await page.evaluate(async()=>{const s=await(await fetch('/api/session')).json();return await(await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json','X-Secops-CSRF':s.csrf},body:JSON.stringify({case:'case-04',request_id:crypto.randomUUID(),previous:null})})).json();});
  assert.equal(duplicate.run_id,await page.locator('#history').inputValue());
  checks.push('duplicate start returns existing run');
  await page.locator('#actor').fill('Automated browser verification, not human acceptance');
  await page.locator('#action').selectOption('close');assert.equal(await page.locator('#override-warning').isVisible(),true);
  await page.locator('#reason').fill('TEST ONLY: explicit override exercises local record semantics, not a safe recommendation.');
  await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#decision-status').textContent.toLowerCase().includes('close'));
  assert.match(await page.locator('#recommendation-title').innerText(),/Escalate/i);
  checks.push('explicit override saved separately from original escalation recommendation');
  await scripted(page,3);assert.match(await page.locator('#evidence-status').innerText(),/Needs review/);
  assert.match(await page.locator('#trace').innerText(),/Unavailable/i);
  await page.screenshot({path:path.join(root,'missing-telemetry.png'),fullPage:true});
  checks.push('real scripted incomplete sign-in retains unavailable telemetry');
  await scripted(page,7);assert.match(await page.locator('#recommendation-title').innerText(),/Close/i);
  checks.push('real scripted endpoint close case');
  // These are isolated presentation fixtures ONLY, never saved or counted as model executions.
  await choose(page,4);await ready(page);
  const id=await page.locator('#history').inputValue();
  const saved=await page.evaluate(async id=>await(await fetch(`/api/runs/${id}`)).json(),id);
  await other.close();
  let fixture=structuredClone(saved);
  fixture.packet.agent_assessment.recommendation='close';
  fixture.policy.recommendation='escalate';
  fixture.packet.agent_assessment.findings[0].summary='<img src=x onerror=alert(1)> presentation test';
  await page.route(`**/api/runs/${id}`,route=>route.fulfill({json:fixture}));
  await page.reload();await ready(page);
  assert.equal(await page.locator('#disagreement').isVisible(),true);
  await page.locator('#raw-assessment summary').click();
  assert.ok((await page.locator('#model-findings').innerText()).includes('<img src=x'));
  assert.equal(await page.locator('#model-findings img').count(),0);
  checks.push('PRESENTATION FIXTURE ONLY: disagreement visible and untrusted source text stays text');
  fixture={...saved,packet:null,policy:null,dispatch:'stopped',state:'failed',trace:saved.trace.slice(0,1),evidence:saved.evidence.slice(0,1),handoffs:[],reviews:[]};
  await page.reload();await page.locator('#stopped').waitFor();
  assert.match(await page.locator('#trace-caption').innerText(),/Recorded/);
  assert.equal(await page.locator('#packet-content').isHidden(),true);
  checks.push('PRESENTATION FIXTURE ONLY: stopped partial trace says recorded, assessment hidden');
  fixture={...saved,packet:null,policy:null,engine_current:false,historical_unverifiable:true};
  await page.reload();await page.locator('#historical').waitFor();
  assert.equal(await page.locator('#stopped').isHidden(),true);
  assert.equal(await page.locator('#packet-content').isHidden(),true);
  checks.push('PRESENTATION FIXTURE ONLY: stale build retains trace, assessment unavailable');
  assert.deepEqual(errors,[]);
  checks.push('no JavaScript exceptions or external browser requests');
} catch(e) { failures.push(e.stack);process.exitCode=1; }
finally {
  if(browser)await browser.close();await stop();
  const result={schema_version:1,execution:'offline browser automation; real scripted SDK where stated; no live model',human_acceptance:false,aws_deployment:false,playwright:require('playwright/package.json').version,checks,errors,failures,passed:!failures.length&&!errors.length};
  fs.writeFileSync(path.join(root,'browser-result.json'),JSON.stringify(result,null,2),{mode:0o600});
  console.log(JSON.stringify(result,null,2));
}
})();
