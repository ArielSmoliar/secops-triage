/* Read-only UI close-ups of the original saved scripted run. No execution or edits. */
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');const {spawn}=require('node:child_process');const assert=require('node:assert/strict');const crypto=require('node:crypto');
const source=path.resolve(process.argv[2]||'');const output=path.resolve(process.argv[3]||'');
if(!process.argv[2]||!process.argv[3]||fs.existsSync(output))throw Error('existing source workspace and new output required');
fs.mkdirSync(output,{recursive:true,mode:0o700});fs.cpSync(source,path.join(output,'workspace'),{recursive:true,errorOnExist:true});
function privateTree(dir){fs.chmodSync(dir,0o700);for(const e of fs.readdirSync(dir,{withFileTypes:true})){const f=path.join(dir,e.name);if(e.isDirectory())privateTree(f);else if(e.isFile())fs.chmodSync(f,0o600);else throw Error('unexpected file type in workspace copy');}}
privateTree(path.join(output,'workspace'));
let child,browser;const errors=[];const shots=[];
(async()=>{try{
 child=spawn(path.resolve('.venv/bin/python'),['-m','secops_triage.workspace','--root',path.join(output,'workspace'),'--port','0'],{stdio:['ignore','pipe','pipe']});
 const origin=await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('startup timeout')),15000);child.stdout.on('data',d=>{const m=String(d).match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(t);resolve(m[0]);}});child.once('exit',()=>reject(Error('startup failed')));});
 browser=await chromium.launch({headless:true,channel:'chrome'});const c=await browser.newContext({viewport:{width:1280,height:1600},deviceScaleFactor:2,reducedMotion:'reduce'});
 await c.route('**/*',r=>r.request().method()==='GET'&&r.request().url().startsWith(origin+'/')?r.continue():(errors.push('blocked non-read-only request'),r.abort()));
 const p=await c.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto(origin);await p.waitForFunction(()=>!document.querySelector('#packet-content').hidden);
 const runId=await p.locator('#history').inputValue();const read=()=>p.evaluate(async id=>await(await fetch('/api/runs/'+id)).json(),runId);const before=await read();
 assert.equal(before.evidence.length,9);assert.equal(before.sessions.length,1);assert.equal(before.handoffs.length,1);assert.equal(before.reviews.length,0);
 async function save(name,selector){const target=p.locator(selector);await target.screenshot({path:path.join(output,name+'.png')});shots.push({name,selector,text:await target.innerText(),sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(output,name+'.png'))).digest('hex')});}
 async function range(name,container,first,last){await p.locator(container).scrollIntoViewIfNeeded();const clip=await p.locator(container).evaluate((el,keys)=>{const dt=[...el.querySelectorAll('dt')];const a=dt.find(x=>x.textContent===keys[0]);const z=keys[1]?dt.find(x=>x.textContent===keys[1]).nextElementSibling:el;const r=el.getBoundingClientRect(),top=a.getBoundingClientRect().top,bottom=z.getBoundingClientRect().bottom;return {x:r.x,y:top,width:r.width,height:bottom-top};},[first,last]);await p.screenshot({path:path.join(output,name+'.png'),clip});shots.push({name,selector:container,field_range:[first,last],clip,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(output,name+'.png'))).digest('hex')});}
 await range('message-training-detail','#messages>.message:first-child','URL',null);await range('message-followup-detail','#messages>.message:last-child','URL',null);
 await save('trace','#trace');await save('messages','#messages');await save('handoff','#saved-records');await save('recommendation','.recommendation');
 await p.getByRole('button',{name:'Inspect scoped authorization',exact:true}).click();await save('authorization','#source-detail');await p.locator('#close-source').click();
 await p.getByRole('button',{name:'View indicator: intelligence-exact-followup',exact:true}).click();await save('intelligence','#source-detail');await range('intelligence-detail','#source-records','match basis','verdict');
 const after=await read();assert.deepEqual(after.sessions,before.sessions);assert.deepEqual(after.handoffs,before.handoffs);assert.deepEqual(after.reviews,before.reviews);assert.deepEqual(after.evidence,before.evidence);assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(output,'spotlight-evidence.json'),JSON.stringify({run_id:runId,packet_hash:before.packet.packet_hash,execution:'Read-only magnified UI stills from original saved scripted run; no new execution',evidence_reads:9,new_sessions:0,new_handoffs:0,shots,errors},null,2),{mode:0o600});console.log('Read-only source close-ups saved.');
}catch(e){fs.writeFileSync(path.join(output,'failure.txt'),e.stack,{mode:0o600});console.error('Spotlight capture failed; evidence preserved.');process.exitCode=1;}finally{if(browser)await browser.close();if(child&&child.exitCode===null){const ended=new Promise(r=>child.once('exit',r));child.kill('SIGINT');await ended;}}})();
