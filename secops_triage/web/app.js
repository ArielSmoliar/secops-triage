'use strict';
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
const labels = {inspect_incident:'Inspect incident',lookup_entity:'Look up entity',query_activity:'Query activity',find_related_cases:'Find related cases'};
const familyNames = {sign_in:'Sign-in',phishing:'Phishing',endpoint:'Endpoint'};
const human = value => String(value ?? '').replaceAll('_',' ');
const decisionName = value => value === 'close' ? 'Close' : value === 'escalate' ? 'Escalate' : 'Needs review';
let csrf = '', catalog = [], selectedCase = 'case-04', run = null, selectedRun = null, poll = null, packetKey = '', renderKey = '', lastAnnouncement = '', sourceReturn = null, saving = false, requestKey = null, selectedSource = null, navigation = 0, savedKey = '', historyKey = '';
function announce(text) { if (text !== lastAnnouncement) { $('announce').textContent = text; lastAnnouncement = text; } }
async function api(path, body) {
  const options = {credentials:'same-origin',cache:'no-store'};
  if (body !== undefined) Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-Secops-CSRF':csrf},body:JSON.stringify(body)});
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Workspace request failed.');
  return value;
}
function error(text) { $('global-error').textContent = text; $('global-error').hidden = !text; }
function draftKey() { return run ? `secops-draft-${run.run_id}-${run.packet?.packet_hash || 'pending'}` : null; }
function fields() { return {actor:$('actor').value,action:$('action').value,reason:$('reason').value,missing:$('missing').value,next:$('next-action').value}; }
function saveDraft() { const key = draftKey(); if (key) { try { sessionStorage.setItem(key, JSON.stringify(fields())); } catch { /* Browser storage may be disabled; form remains intact. */ } } }
function restoreDraft() {
  let draft = null;
  try { draft = JSON.parse(sessionStorage.getItem(draftKey())); } catch { /* Treat absent browser drafts as empty. */ }
  $('actor').value = draft?.actor || '';
  $('action').value = draft?.action || 'handoff';
  $('reason').value = draft?.reason || '';
  $('missing').value = draft?.missing || '';
  $('next-action').value = draft?.next || '';
  $('save-error').hidden = true;
  requestKey = null;
  updateAction();
}
async function loadCatalog() {
  const data = await api('/api/cases'); catalog = data.cases;
  const list = $('case-list'); list.replaceChildren();
  for (const item of catalog) {
    const b = el('button', null, 'case'); b.type = 'button'; b.setAttribute('aria-current', String(item.id === selectedCase));
    const meta = el('span', null, 'case-meta'); meta.append(el('span', familyNames[item.family] || human(item.family)),el('span',item.id.replace('case-','#')));
    b.append(meta,el('span',item.title,'case-title'));
    if (item.latest_run) b.append(el('span','Saved execution available','saved-indicator'));
    if (item.interrupted_starts) b.append(el('span',`${item.interrupted_starts} interrupted start retained`,'saved-indicator'));
    b.addEventListener('click',()=>selectCase(item.id)); list.append(b);
  }
}
async function selectCase(id, explicitRun=null) {
  const navigationId = ++navigation; saveDraft(); clearTimeout(poll); selectedCase = id; selectedRun = explicitRun; run = null; packetKey = ''; renderKey = ''; savedKey = ''; historyKey = '';
  $('source-detail').hidden = true; selectedSource = null; $('revision-confirm').hidden = true;
  $('run-content').hidden = true; $('packet-content').hidden = true; $('empty').hidden = false;
  $('save-error').hidden = true; $('history-label').hidden = true; error('');
  await loadCatalog();
  if (navigationId !== navigation) return;
  const item = catalog.find(x=>x.id === id);
  $('incident-source').textContent = `${item.source} / ${item.incident_id} · ${familyNames[item.family] || human(item.family)}`;
  $('incident-title').textContent = item.title;
  $('incident-meta').textContent = 'Existing incident · synthetic source snapshot · source status unchanged';
  $('run-view').textContent = 'No run started';
  $('start').hidden = Boolean(item.latest_run); $('start').disabled = false; $('start').textContent = 'Run scripted investigation';
  $('new-revision').hidden = !item.latest_run;
  selectedRun = explicitRun || item.latest_run;
  if (selectedRun) await refresh();
}
async function start(previous=null) {
  $('start').disabled = true; $('confirm-revision').disabled = true; error('');
  try {
    const result = await api('/api/start',{case:selectedCase,request_id:crypto.randomUUID(),previous});
    $('revision-confirm').hidden = true;
    await selectCase(selectedCase,result.run_id);
    announce('Scripted Strands investigation started. Source SIEM remains unchanged.');
  } catch (e) { error(e.message); $('start').disabled = false; }
  finally { $('confirm-revision').disabled = false; }
}
function citation(evidenceId, text, eventId=null) {
  const button = el('button',text,'citation'); button.type='button';
  button.addEventListener('click',()=>openSource(evidenceId,eventId,button)); return button;
}
function sourceLabel(evidenceId,eventId) {
  const record = run?.evidence.find(e=>e.id===evidenceId);
  const event = record?.result.records.find(e=>e.id===eventId);
  return event ? `View ${human(event.kind)}: ${event.id}` : `View ${human(record?.request.template || record?.tool || 'query result')}`;
}
function openSource(evidenceId,eventId,button) {
  const evidence = run.evidence.find(e=>e.id===evidenceId); if (!evidence) return;
  sourceReturn = button; selectedSource = evidenceId;
  $('source-heading').textContent = eventId || human(evidence.request.template || evidence.tool);
  $('source-summary').textContent = `${labels[evidence.tool]} · ${human(evidence.result.outcome)} · ${evidence.result.complete ? 'Complete returned result' : 'Incomplete returned result'} · ${evidence.collected_at}`;
  const target = $('source-records'); target.replaceChildren();
  const records = eventId ? evidence.result.records.filter(e=>e.id===eventId) : evidence.result.records;
  if (!records.length) target.append(el('p',evidence.result.complete ? 'No event records in this returned query. An empty result is not proof of safety.' : 'This query did not return complete evidence. Missing records must not be treated as a clean result.'));
  if (evidence.result.entity) {
    const section = el('section',null,'source-record'); section.append(el('h3','Entity context'),el('pre',JSON.stringify(evidence.result.entity,null,2))); target.append(section);
  }
  for (const event of records) {
    const section = el('section',null,'source-record'); section.append(el('h3',event.id));
    const dl = el('dl'); const values = {kind:event.kind,occurred_at:event.occurred_at,...event.attributes};
    for (const [key,value] of Object.entries(values)) { dl.append(el('dt',human(key)),el('dd',typeof value==='object' ? JSON.stringify(value,null,2) : String(value))); }
    section.append(dl,el('h3','Original source text · untrusted'),el('p',event.raw_text)); target.append(section);
  }
  $('source-provenance').textContent = JSON.stringify({tool:evidence.tool,request:evidence.request,adapter:evidence.adapter,query_result_metadata:Object.fromEntries(Object.entries(evidence.result).filter(([key])=>!['records','entity'].includes(key))),evidence_id:evidence.id,snapshot_hash:evidence.snapshot_hash,content_sha256:evidence.hash},null,2);
  $('source-detail').hidden = false; $('source-heading').focus();
}
function closeSource() { $('source-detail').hidden = true; selectedSource = null; if (sourceReturn?.isConnected) sourceReturn.focus(); else $('trace-heading').focus(); }
function renderTrace() {
  const list = $('trace'); list.replaceChildren();
  if (!run.trace.length) { const li=el('li','Waiting for the first committed SDK tool call.');list.append(li); }
  run.trace.forEach((item,index)=>{
    const li=el('li'); const step=el('span',null,'step'); step.append(el('span',`${String(index+1).padStart(2,'0')} · ${item.at.slice(11,19)}`),el('span',human(item.state)));
    const title = human(item.request.template || item.request.entity_id || labels[item.tool]);
    const control = item.evidence_id ? citation(item.evidence_id,title) : el('span',title);
    li.append(step,control,el('span',item.tool,'tool'));
    if (item.evidence_id) li.append(el('span',`${item.record_count} records · ${human(item.outcome)}${item.complete ? '' : ' · incomplete'}`,'small muted'));
    list.append(li);
  });
  $('trace-count').textContent = `${run.evidence.length} recorded reads · ${new Set(run.trace.map(x=>x.tool)).size} scoped tools`;
  $('trace-caption').textContent = ['reserved','running'].includes(run.dispatch) ? 'Live view of committed calls from the scripted SDK run. No simulated progress or invented reasoning.' : 'Recorded SDK calls from this saved execution, including retained partial work. Viewing this trace does not rerun it.';
}
function renderMessages() {
  const events = new Map();
  for (const evidence of run.evidence) for (const event of evidence.result.records) if (event.kind==='message') events.set(event.id,{event,evidence});
  $('message-section').hidden = events.size<2; $('messages').replaceChildren();
  [...events.values()].sort((a,b)=>a.event.occurred_at.localeCompare(b.event.occurred_at)).forEach(({event,evidence},index)=>{
    const panel=el('article',null,'message');panel.append(el('div',`MESSAGE ${index+1}`,'eyebrow'),el('h3',event.id));const dl=el('dl');
    const a=event.attributes;
    for(const [key,value] of Object.entries({Time:event.occurred_at,Sender:a.sender,Subject:a.subject,URL:(a.observables || []).map(o=>o.value).join('\n'),Message:a.message_id ?? event.id})) if(value!==undefined)dl.append(el('dt',key),el('dd',typeof value==='object'?JSON.stringify(value):value));
    const allRecords=run.evidence.flatMap(e=>e.result.records.map(r=>({r,e})));
    const deliveries=allRecords.filter(x=>x.r.kind==='delivery'&&x.r.attributes.message_id===event.id);
    const clicks=allRecords.filter(x=>x.r.kind==='click'&&x.r.attributes.message_id===event.id);
    dl.append(el('dt','Retrieved activity'),el('dd',`${deliveries.length} delivery record${deliveries.length===1?'':'s'} · ${clicks.length} click record${clicks.length===1?'':'s'}`));
    panel.append(dl,citation(evidence.id,'Inspect this message',event.id));
    for(const item of [...deliveries,...clicks])panel.append(el('br'),citation(item.e.id,`View ${human(item.r.kind)}: ${item.r.id}`,item.r.id));
    const approvals=allRecords.filter(x=>x.r.kind==='authorization'&&x.r.attributes.target_id===event.id);
    for(const item of approvals){panel.append(el('p',`Scoped authorization: ${item.r.attributes.reference} (${item.r.attributes.status}). Applies to ${(item.r.attributes.authorized_event_ids||[]).join(', ')}.`,'small'),citation(item.e.id,'Inspect scoped authorization',item.r.id));}
    if(!approvals.length)panel.append(el('p','No retrieved authorization record targets this message. Inspect business-context coverage before inferring absence.','small muted'));
    $('messages').append(panel);
  });
}
function renderPacket() {
  const p=run.packet; $('packet-content').hidden=!p;if(!p)return;
  const names={escalate:'Escalate for further investigation',close:'Documented activity supports a local close'};
  $('recommendation-title').textContent=names[p.recommendation] || 'Keep the investigation unresolved';
  const reasonText={suspicious_evidence:'Retrieved evidence supports further investigation. Impact and compromise are not established.',documented_expected_activity:'Activity falls within the retrieved authorization scope. Review its source and limits before deciding.',missing_evidence:'Required context is missing or incomplete. Missing evidence is not a benign result.',legitimacy_not_established:'The retrieved evidence does not establish expected business activity.'};
  $('recommendation-reason').textContent=reasonText[p.alerts[0]?.reason] || 'Review the supporting records and open questions.';
  $('model-recommendation').textContent=decisionName(p.agent_assessment?.recommendation);
  $('policy-recommendation').textContent=decisionName(run.policy.recommendation);
  $('final-recommendation').textContent=decisionName(p.recommendation);
  $('disagreement').hidden=p.agent_assessment?.recommendation===(run.policy.recommendation || 'needs_review');
  $('model-findings').replaceChildren();
  for(const f of p.agent_assessment?.findings || []) { const line=el('div',null,'observation');line.append(el('p',f.summary),citation(f.evidence_id,sourceLabel(f.evidence_id,f.event_id),f.event_id));$('model-findings').append(line); }
  renderMessages();
  const groups=[['suspicious','Supports escalation'],['benign_context','Supports authorized activity'],['context','Additional context']];
  const observations=p.alerts.flatMap(a=>a.observations);const observedRoles=new Set(observations.map(o=>o.role));
  // The store's role vocabulary is source-defined; preserve other roles visibly.
  for(const role of observedRoles)if(!groups.some(x=>x[0]===role))groups.push([role,human(role)]);
  $('evidence-groups').replaceChildren();
  for(const [role,title] of groups){const section=el('section',null,'evidence-group');section.append(el('h3',title));const items=observations.filter(o=>o.role===role);if(!items.length)section.append(el('p','No finding in this group. This is not proof of absence.','small muted'));for(const o of items){const line=el('div',null,'observation');line.append(el('p',o.text),citation(o.evidence_id,sourceLabel(o.evidence_id,o.event_id),o.event_id));section.append(line);} $('evidence-groups').append(section);}
  $('gaps').replaceChildren();const gaps=p.alerts.flatMap(a=>a.gaps);
  if(!gaps.length)$('gaps').append(el('p','No required collection gap was recorded by the bounded policy. Source truth, impact and real-world completeness are not independently established.','small muted'));
  for(const gap of gaps){const node=el('div',null,'gap');node.append(el('strong',human(gap.check)),el('p',gap.reason.split(',').map(human).join('; ')));if(gap.evidence_id)node.append(citation(gap.evidence_id,'Inspect this unresolved query'));$('gaps').append(node);}
  if(catalog.find(c=>c.id===selectedCase)?.family==='phishing')$('gaps').append(el('p','Delivery and clicks do not establish credential submission or account compromise. Follow-on identity telemetry is outside this playbook and was not queried.','small muted'));
  $('next-checks').replaceChildren();for(const text of new Set(p.alerts.flatMap(a=>a.next_checks)))$('next-checks').append(el('li',text));
  $('entities').replaceChildren();for(const e of run.evidence){const entity=e.result.entity;if(entity)$('entities').append(el('div',`${entity.name} · ${entity.kind} · ${entity.owner}`,'entity'));}
  const records=new Map();for(const e of run.evidence)for(const r of e.result.records)if(!records.has(r.id))records.set(r.id,{r,e});
  $('timeline').replaceChildren();for(const {r,e} of [...records.values()].sort((a,b)=>a.r.occurred_at.localeCompare(b.r.occurred_at)||a.r.id.localeCompare(b.r.id))){const li=el('li');li.append(el('time',r.occurred_at),citation(e.id,`${human(r.kind)} · ${r.id}`,r.id));$('timeline').append(li);}
  $('coverage').replaceChildren();for(const e of run.evidence){const row=el('div',null,'coverage-row');row.append(citation(e.id,human(e.request.template||e.tool)),el('span',`${human(e.result.outcome)} · ${e.result.complete?'complete':'incomplete'} · ${e.result.records.length} records`));$('coverage').append(row);}
  $('packet-identity').textContent=`Run ${p.run_id}\nPacket SHA-256 ${p.packet_hash}\nSnapshot ${p.snapshot_hash}\nHashes establish integrity, not truth.`;
  restoreDraft();
}
function renderSaved() {
  const records=[...run.reviews.map(r=>({...r,kind:r.disposition})),...run.handoffs.map(h=>({...h,kind:'unresolved handoff'}))].sort((a,b)=>a.at.localeCompare(b.at));
  const target=$('saved-records'); const currentSavedKey=JSON.stringify(records);
  if(currentSavedKey!==savedKey){ savedKey=currentSavedKey;target.replaceChildren();
  for(const record of records){const item=el('article',null,'saved-record');item.append(el('strong',`${record.current?'Saved locally':'Historical'} · ${human(record.kind)}`),el('span',`${record.actor} · ${record.at}`,'stamp'),el('p',record.reason));if(record.missing_context)item.append(el('p',`Missing context: ${record.missing_context}`),el('p',`Next action: ${record.next_action}`));target.append(item);}}
  const current=records.filter(r=>r.current).at(-1);$('copy-note').hidden=!current;
  $('copy-note').onclick=async()=>{const text=current ? `${current.kind.toUpperCase()} · ${run.source.source} / ${run.source.incident_id}\n${current.reason}\n${current.missing_context ? `Missing: ${current.missing_context}\nNext: ${current.next_action}\n` : ''}Recorded by ${current.actor} at ${current.at}\nRun ${run.run_id}; packet ${(run.packet?.packet_hash || run.recorded_packet_hash)}\nLocal record only; SIEM unchanged.` : '';try{await navigator.clipboard.writeText(text);$('copy-result').textContent='Saved case note copied.';}catch{$('copy-result').textContent='Clipboard unavailable. Select and copy the saved note above.';}};
  $('decision-status').textContent=run.reviews.some(r=>r.current)?`Local ${human(run.reviews.find(r=>r.current).disposition)} recorded`:run.handoffs.some(h=>h.current)?'Unresolved handoff saved':'Not recorded';
  const locked=!run.packet || !run.is_latest || !run.engine_current || run.state==='reviewed';
  for(const control of $('decision-form').elements)control.disabled=locked || saving;
  if(!run.engine_current){$('save-error').hidden=false;$('save-error').textContent='The investigation build changed. The historical packet cannot be revalidated under this build. Evidence remains visible; create a new explicit revision before saving.';}
  updateAction();
}
function updateAction(){const handoff=$('action').value==='handoff';$('handoff-fields').hidden=!handoff;$('missing').required=handoff;$('next-action').required=handoff;$('save').textContent=handoff?'Save unresolved handoff':$('action').value==='close'?'Record local close decision':'Record local escalation';$('override-warning').hidden=handoff || !run?.packet || $('action').value===run.packet.recommendation;}
function renderHistory(){const item=catalog.find(c=>c.id===selectedCase);$('history-label').hidden=!item?.runs.length;const history=$('history');const key=JSON.stringify([item?.runs,run.run_id]);if(key===historyKey)return;historyKey=key;history.replaceChildren();for(const [i,id] of (item?.runs||[]).entries()){const option=el('option',`${i+1}${id===item.latest_run?' · latest':' · historical'} · ${id.slice(0,8)}`);option.value=id;option.selected=id===run.run_id;history.append(option);}}
async function refresh(){const wanted=selectedRun;try{const value=await api(`/api/runs/${wanted}`);if(wanted!==selectedRun)return;run=value;error('');$('run-content').hidden=false;$('empty').hidden=true;$('start').hidden=true;$('new-revision').hidden=false;const active=['reserved','running'].includes(run.dispatch)&&!run.packet;$('new-revision').disabled=active||!run.is_latest;$('run-view').textContent=active?'Executing now · scripted':'Saved execution · no rerun';$('run-mode').textContent='Scripted provider · real Strands SDK';$('incident-meta').textContent=`Snapshot ${run.source.observed_at} · Evidence window ${run.source.start.slice(11,16)}–${run.source.end.slice(11,16)} UTC`;$('collection-status').textContent=active?`${run.evidence.length} reads committed`:run.packet?'Recorded collection finished':run.historical_unverifiable?'Recorded · build changed':'Stopped / incomplete';$('evidence-status').textContent=run.packet?(run.packet.investigation_status==='complete'?'Required checks complete':'Needs review'):'No completed assessment';$('stale').hidden=run.is_latest;$('stopped').hidden=active||Boolean(run.packet)||run.historical_unverifiable;$('historical').hidden=!run.historical_unverifiable;$('failure-stages').replaceChildren();for(const stage of run.stages)$('failure-stages').append(el('li',`${human(stage.stage)}${stage.label ? ` · ${human(stage.label)}`:''}`));const key=JSON.stringify([run.trace,run.dispatch]);if(key!==renderKey){renderTrace();renderKey=key;}if(run.packet?.packet_hash!==packetKey){packetKey=run.packet?.packet_hash;renderPacket();}renderSaved();renderHistory();announce(active?`${run.evidence.length} evidence reads recorded.`:run.packet?`Investigation ready. ${decisionName(run.packet.recommendation)}. ${human(run.packet.investigation_status)}.`:run.historical_unverifiable?'Historical build; retained evidence available.':'Investigation stopped. Retained evidence is available.');}catch(e){error(e.message);$('run-view').textContent='Last verified view · refresh unavailable';for(const control of $('decision-form').elements)control.disabled=true;$('new-revision').disabled=true;}finally{if(wanted===selectedRun){clearTimeout(poll);poll=setTimeout(refresh,run && ['reserved','running'].includes(run.dispatch)?350:2500);}}}
$('start').onclick=()=>start();$('new-revision').onclick=()=>{$('revision-confirm').hidden=false;$('confirm-revision').focus();};$('cancel-revision').onclick=()=>{$('revision-confirm').hidden=true;$('new-revision').focus();};$('confirm-revision').onclick=()=>start(run.run_id);$('history').onchange=e=>selectCase(selectedCase,e.target.value);$('open-latest').onclick=()=>selectCase(selectedCase,run.latest_run);$('close-source').onclick=closeSource;document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('source-detail').hidden)closeSource();});$('about-toggle').onclick=()=>{const show=$('about').hidden;$('about').hidden=!show;$('about-toggle').setAttribute('aria-expanded',String(show));};
for(const control of $('decision-form').elements)control.addEventListener('input',()=>{saveDraft();requestKey=null;updateAction();});
$('decision-form').addEventListener('submit',async event=>{event.preventDefault();if(saving||!run?.packet)return;saveDraft();saving=true;$('save-error').hidden=true;const currentId=run.run_id;requestKey ||= crypto.randomUUID();const body={packet_hash:run.packet.packet_hash,actor:$('actor').value.trim(),reason:$('reason').value.trim(),action:$('action').value,request_id:requestKey};if(body.action==='handoff')Object.assign(body,{missing_context:$('missing').value.trim(),next_action:$('next-action').value.trim()});renderSaved();try{await api(`/api/runs/${currentId}/decision`,body);announce('Local record saved. Source SIEM unchanged.');if(run?.run_id===currentId){clearTimeout(poll);await refresh();}}catch(e){$('save-error').textContent=e.message;$('save-error').hidden=false;announce('Save failed. Your draft is preserved.');}finally{saving=false;if(run?.run_id===currentId)renderSaved();}});
(async()=>{try{csrf=(await api('/api/session')).csrf;await selectCase('case-04');}catch(e){error(`${e.message} Reload this page after restarting the local workspace.`);}})();
