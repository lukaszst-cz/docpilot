const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let current = null, currentChange = null, pickerBusy = false, deferredInstallPrompt = null, setupState = null;
const titles = {
  dashboard:['Dashboard','Documents + Deadlines + Actions + Archive'], inbox:['Smart Inbox','Analyze, classify, rename and organize'], review:['Review Queue','Documents that need a human decision'],
  documents:['Documents','Your local document index'], deadlines:['Deadline Radar','Payments, replies, expirations and warranties'],
  duplicates:['Duplicates','Exact and near-duplicate detection'], cases:['Cases & Timeline','Group related documents into one story'],
  search:['Search & Q&A','Search locally by meaning and ask factual questions'], tools:['Tools','Diff, batch import, redaction and document health'],
  automation:['Automation','Watch folders, rules, profiles and custom types'], exports:['Exports','Calendar, Obsidian, Notion and backup'],
  settings:['Settings','Data, diagnostics, privacy and integrations']
};

function esc(v=''){return String(v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function fmtDate(v){if(!v)return '—'; try{return new Date(v+'T00:00:00').toLocaleDateString();}catch{return v}}
function money(md){return md?.amount==null?'—':`${md.amount} ${md.currency||''}`.trim()}

function friendlyApiMessage(status, detail=''){
  if(status===413)return detail || 'This file is larger than DocPilot allows. Choose a smaller file or split the document first.';
  if(status===403)return 'DocPilot blocked a request that did not come from this local app.';
  if(status===404)return detail || 'The selected file or resource is no longer available. Choose it again.';
  if(status>=500)return 'DocPilot hit a local error. Open Settings → Data & diagnostics, then check the log if the problem repeats.';
  return detail || `DocPilot could not complete this action (HTTP ${status}).`;
}
function showAppNotice(message,type='error'){
  const box=$('#appNotice');
  if(!box)return;
  box.textContent=message;
  box.className=`appNotice ${type}`;
  box.setAttribute('role',type==='error'?'alert':'status');
  box.setAttribute('aria-live',type==='error'?'assertive':'polite');
  window.clearTimeout(showAppNotice.timer);
  showAppNotice.timer=window.setTimeout(()=>box.classList.add('hidden'),7000);
}
function runLoad(task){
  return Promise.resolve().then(task).catch(e=>{showAppNotice(e.message);return null});
}
function renderSetupStatus(s){
  setupState=s;
  const card=$('#setupCard'), list=$('#setupChecklist'), welcome=$('#welcomeCard');
  if(!card||!list)return;
  const diskOk=Number(s.free_space_gb||0)>=Number(s.recommended_free_space_gb||2);
  const visible=!s.complete&&!s.has_documents;
  card.classList.toggle('hidden',!visible);
  if(visible&&welcome)welcome.classList.add('hidden');
  list.innerHTML=[
    ['Local storage','Ready',s.data_root,'ok'],
    ['OCR',s.ocr?.ready?'Ready':'Needs attention',s.ocr?.ready?`Tesseract ${s.ocr.version||''}`:'Scanned images may not be readable until OCR is available.',s.ocr?.ready?'ok':'warn'],
    ['Disk space',diskOk?'Ready':'Low space',`${s.free_space_gb} GB free · ${s.recommended_free_space_gb} GB recommended`,diskOk?'ok':'warn'],
    ['Safe demo',s.demo_ready?'Ready':'Missing',s.demo_ready?'Synthetic sample is available.':'Bundled demo file could not be found.',s.demo_ready?'ok':'warn']
  ].map(([name,state,detail,kind])=>`<div class="setupItem"><div><strong>${esc(name)}</strong><small>${esc(detail)}</small></div><span class="setupState ${kind}">${esc(state)}</span></div>`).join('');
}
async function loadSetupStatus(){
  try{renderSetupStatus(await api('/api/setup/status'))}
  catch(e){showAppNotice(e.message)}
}
async function setSetupComplete(complete){
  const s=await api('/api/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({complete})});
  renderSetupStatus(s);
  return s;
}

$('.navBtn').forEach(b=>b.addEventListener('click',()=>go(b.dataset.view)));
$('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go)));
$('#nav')?.addEventListener('keydown',e=>{
  if(!['ArrowDown','ArrowUp','ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;
  const items=$('.navBtn');
  const currentIndex=Math.max(0,items.indexOf(document.activeElement));
  let next=currentIndex;
  if(e.key==='Home')next=0;
  else if(e.key==='End')next=items.length-1;
  else if(e.key==='ArrowDown'||e.key==='ArrowRight')next=(currentIndex+1)%items.length;
  else next=(currentIndex-1+items.length)%items.length;
  e.preventDefault();
  items[next]?.focus();
});
$('#quickImportBtn').addEventListener('click',()=>{go('inbox',{focus:false}); setTimeout(selectLocalFile,100)});
$('#tryDemoBtn')?.addEventListener('click',async()=>{
  const btn=$('#tryDemoBtn'), status=$('#demoStatus');
  btn.disabled=true; btn.textContent='Loading demo…'; status.textContent='';
  try{
    const d=await api('/api/demo',{method:'POST'});
    status.textContent='Demo loaded. Opening Documents…';
    await loadDashboard();
    setTimeout(()=>go('documents'),350);
  }catch(e){
    status.textContent=e.message;
  }finally{
    btn.disabled=false; btn.textContent='Try safe demo';
  }
});
$('#setupDemoBtn')?.addEventListener('click',async()=>{
  const btn=$('#setupDemoBtn'), msg=$('#setupMessage');
  btn.disabled=true; msg.textContent='Loading the safe demo…';
  try{
    await api('/api/demo',{method:'POST'});
    await setSetupComplete(true);
    msg.textContent='Demo loaded. You can explore Documents now.';
    await loadDashboard();
    go('documents');
  }catch(e){msg.textContent=e.message;showAppNotice(e.message)}
  finally{btn.disabled=false}
});
$('#setupDocumentBtn')?.addEventListener('click',()=>{go('inbox',{focus:false});setTimeout(selectLocalFile,100)});
$('#setupDoneBtn')?.addEventListener('click',async()=>{
  try{await setSetupComplete(true);await loadDashboard()}
  catch(e){showAppNotice(e.message)}
});
$('#setupResetBtn')?.addEventListener('click',async()=>{
  try{await setSetupComplete(false);go('dashboard');await loadDashboard()}
  catch(e){showAppNotice(e.message)}
});
function go(name,{focus=true}={}){
  const target=$(`#view-${name}`);
  if(!target||!titles[name])return;
  $('.navBtn').forEach(b=>{
    const active=b.dataset.view===name;
    b.classList.toggle('active',active);
    if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');
  });
  $('.view').forEach(v=>v.classList.remove('activeView'));
  target.classList.add('activeView');
  $('#viewTitle').textContent=titles[name][0];
  $('#viewSubtitle').textContent=titles[name][1];
  if(focus)requestAnimationFrame(()=>$('#viewTitle')?.focus({preventScroll:true}));
  if(name==='dashboard')runLoad(loadDashboard);
  if(name==='review')runLoad(loadReview);
  if(name==='documents')runLoad(loadDocuments);
  if(name==='deadlines')runLoad(loadDeadlines);
  if(name==='duplicates')runLoad(loadDuplicates);
  if(name==='cases')runLoad(loadCases);
  if(name==='automation'){runLoad(loadRules);runLoad(loadTypes);runLoad(loadWatch)}
  if(name==='settings'){runLoad(loadIntegrationStatus);runLoad(loadNotificationStatus);runLoad(loadDiagnostics)}
}

window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredInstallPrompt=e;$('#installPwaBtn').classList.remove('hidden')});
async function installPwa(){if(!deferredInstallPrompt){showAppNotice('Use your browser menu and choose Install app / Install DocPilot if the install option is available.','ok');return}deferredInstallPrompt.prompt();await deferredInstallPrompt.userChoice;deferredInstallPrompt=null;}
$('#installPwaBtn').addEventListener('click',installPwa);$('#installPwaBtn2').addEventListener('click',installPwa);
if('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(()=>{});

async function api(url,opts={}){const r=await fetch(url,{cache:'no-store',...opts});if(!r.ok){let detail='';try{const j=await r.json();detail=j.detail||''}catch{}const err=new Error(friendlyApiMessage(r.status,detail));err.status=r.status;throw err}return r.headers.get('content-type')?.includes('application/json')?r.json():r.text()}

async function loadDashboard(){const d=await api('/api/dashboard');const welcome=$('#welcomeCard');const setupActive=setupState&&!setupState.complete&&!setupState.has_documents;if(welcome)welcome.classList.toggle('hidden',d.documents>0||setupActive);$('#stats').innerHTML=[['Documents',d.documents],['Deadlines',d.deadline_count],['Actions',d.actions],['Duplicate groups',d.duplicate_groups],['Cases',d.cases],['Health alerts',d.unhealthy]].map(([a,b])=>`<div class="stat"><strong>${b}</strong><span>${a}</span></div>`).join('');$('#dashboardDeadlines').innerHTML=d.deadlines.length?d.deadlines.slice(0,8).map(x=>`<div class="listItem"><div class="listItemHead"><strong>${esc(x.name)}</strong><span class="badge ${x.days<0?'red':x.days<=3?'warn':''}">${x.days<0?`${Math.abs(x.days)}d overdue`:x.days===0?'today':`${x.days}d`}</span></div><div class="meta"><span>${fmtDate(x.date)}</span><span>${esc(x.action||'deadline')}</span></div></div>`).join(''):'<p class="muted">No detected deadlines yet.</p>';$('#dashboardActions').innerHTML=d.actions?`<div class="stat"><strong>${d.actions}</strong><span>documents require an action</span></div><p class="muted">Use Documents and Deadline Radar to review them.</p>`:'<p class="muted">Nothing marked as action-required.</p>';$('#featureGrid').innerHTML=[['OCR','PL/EN local OCR'],['Smart Inbox','classify + rename'],['Deadline Radar','dates + actions'],['Duplicates','SHA-256 + near match'],['Cases','timeline'],['Search','local vector + Q&A'],['Review Queue','human-in-the-loop'],['Redaction','text + scanned PDF'],['PWA','installable UI']].map(([a,b])=>`<div class="feature"><strong>${a}</strong><small>${b}</small></div>`).join('')}

const drop=$('#dropZone'), browse=$('#browseBtn');browse.addEventListener('click',selectLocalFile);['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>{const f=e.dataTransfer.files[0];if(f)analyzeCopy(f)});
async function selectLocalFile(){if(pickerBusy)return;pickerBusy=true;browse.disabled=true;browse.textContent='Opening Windows picker…';try{const d=await api('/api/select-local',{method:'POST'});if(!d.cancelled){current=d;showAnalysis(d)}}catch(e){showAppNotice(e.message)}finally{pickerBusy=false;browse.disabled=false;browse.textContent='Select file on this PC'}}
async function analyzeCopy(file){const fd=new FormData();fd.append('upload',file);try{const d=await api('/api/analyze',{method:'POST',body:fd});current=d;showAnalysis(d)}catch(e){showAppNotice(e.message)}}
function showAnalysis(d){drop.classList.add('hidden');$('#successPanel').classList.add('hidden');const md=d.metadata||{};const sensitive=(d.sensitive||[]).map(x=>`${x.type}: ${x.value}`).join(' · ');$('#analysisPanel').classList.remove('hidden');$('#analysisPanel').innerHTML=`<div class="cardHead"><div><span class="badge">ANALYZED</span><h2>${esc(d.source_name)}</h2></div><span>${Math.round((md.confidence||0)*100)}% confidence</span></div><div class="modeNotice ${d.source_mode==='original'?'original':'copy'}">${d.source_mode==='original'?'REAL FILE MODE — Apply can rename or move the original.':'COPY MODE — drag & drop imported a safe copy.'}</div><div class="sourcePath">${esc(d.source_path)}</div><div class="grid"><label>Type<input id="docType" value="${esc(md.document_type||'')}" disabled></label><label>Issuer<input value="${esc(md.issuer||'')}" disabled></label><label>Amount<input value="${esc(money(md))}" disabled></label><label>Deadline<input value="${esc(md.deadline||md.warranty_until||'')}" disabled></label><label>Language<input value="${esc(md.language||'unknown')}" disabled></label><label>Health<input value="${d.health_score}/100" disabled></label><label class="wide">Category<input id="category" value="${esc(d.suggested_category)}"></label><label class="wide">Suggested filename<input id="suggestedFilename" value="${esc(d.suggested_filename)}"></label><label>Profile<select id="profile"><option>Home</option><option>Company</option><option>Child</option><option>Vehicle</option><option>Legal Cases</option></select></label><label>Action<select id="actionRequired"><option value="">None</option><option value="to-pay">To pay</option><option value="to-reply">To reply</option><option value="to-sign">To sign</option><option value="to-review">To review</option><option value="to-archive">To archive</option></select></label><label class="wide">Case<input id="caseName" value="${esc(d.suggested_case||'')}"></label><label class="wide">Apply action<select id="applyMode"><option value="rename">Rename original in the same folder</option><option value="organize">Move + rename into DocPilot archive</option></select></label><label class="wide"><input id="smartStructure" type="checkbox" checked style="width:auto;margin-right:8px"> Smart folder structure (category / year / issuer) when organizing</label></div>${sensitive?`<p class="badge warn">Sensitive data detected</p><p class="muted">${esc(sensitive)}</p>`:''}${(d.health_notes||[]).length?`<p class="muted">Health: ${esc(d.health_notes.join(' · '))}</p>`:''}<div class="actions"><button class="secondary" id="cancelAnalyze">Analyze another</button><button id="applyBtn">Apply</button></div>`;$('#profile').value=d.profile||'Home';$('#actionRequired').value=d.action_required||'';if(d.source_mode!=='original'){$('#applyMode').value='organize';$('#applyMode').disabled=true}$('#cancelAnalyze').addEventListener('click',resetInbox);$('#applyBtn').addEventListener('click',applyCurrent)}
function resetInbox(){current=null;currentChange=null;$('#analysisPanel').classList.add('hidden');$('#successPanel').classList.add('hidden');drop.classList.remove('hidden')}
async function applyCurrent(){
  const mode=$('#applyMode').value;
  const p={source_path:current.source_path,category:$('#category').value,filename:$('#suggestedFilename').value,mode,profile:$('#profile').value,case_name:$('#caseName').value||null,action_required:$('#actionRequired').value||null,smart_structure:$('#smartStructure')?.checked!==false};

  if(current.source_mode==='original'){
    const action=mode==='rename'?'rename the original file':'move the original file into the DocPilot archive';
    const ok=confirm(`DocPilot is about to ${action}.\n\nReview the proposed name and category first. This operation will be recorded in Undo History.\n\nContinue?`);
    if(!ok)return;
  }

  const btn=$('#applyBtn');
  btn.disabled=true;
  btn.textContent='Applying…';
  try{
    currentChange=await api('/api/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
    $('#analysisPanel').classList.add('hidden');
    $('#successPanel').classList.remove('hidden');
    $('#successPanel').innerHTML=`<div class="check">✓</div><h2>Change applied and verified</h2><p class="sourcePath">${esc(currentChange.destination)}</p><div class="successActions"><button class="secondary" id="undoBtn">Undo</button><button class="secondary" id="revealBtn">Show in Explorer</button><button id="anotherBtn">Process another file</button></div>`;
    $('#undoBtn').addEventListener('click',undoCurrent);
    $('#revealBtn').addEventListener('click',()=>reveal(currentChange.destination));
    $('#anotherBtn').addEventListener('click',async()=>{resetInbox();await new Promise(r=>setTimeout(r,100));selectLocalFile()});
  }catch(e){
    showAppNotice(e.message);
    btn.disabled=false;
    btn.textContent='Apply';
  }
}
async function undoCurrent(){try{const r=await api(`/api/undo/${currentChange.id}`,{method:'POST'});showAppNotice(`Restored to: ${r.restored_to}`,'ok');resetInbox()}catch(e){showAppNotice(e.message)}}
async function reveal(path){try{await api('/api/open-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})})}catch(e){showAppNotice(e.message)}}

async function loadReview(){
  const items=await api('/api/review');
  $('#reviewList').innerHTML=items.length?items.map(x=>`<div class="listItem"><div class="listItemHead"><strong>${esc(x.name)}</strong><span class="badge ${x.severity==='high'?'red':'warn'}">${esc(x.severity)}</span></div><div class="meta"><span>${esc(x.category||'')}</span><span>${esc(x.case_name||'')}</span></div>${x.reasons.map(r=>`<div class="reviewReason"><strong>${esc(r.code)}</strong> — ${esc(r.detail)}</div>`).join('')}<div class="actions"><button class="secondary reviewOpen" data-path="${esc(x.path)}">Show file</button></div></div>`).join(''):'<p class="muted">Review Queue is clear.</p>';
  $$('.reviewOpen').forEach(b=>b.addEventListener('click',()=>reveal(b.dataset.path)));
}
$('#refreshReviewBtn')?.addEventListener('click',()=>runLoad(loadReview));

async function loadDocuments(){const docs=await api('/api/documents?limit=1000');$('#documentsTable').innerHTML=docs.length?`<div class="tableWrap"><table><thead><tr><th>Name</th><th>Type</th><th>Deadline</th><th>Profile</th><th>Case</th><th>Action</th><th>Health</th><th></th></tr></thead><tbody>${docs.map(d=>`<tr><td><strong>${esc(d.source_name)}</strong><div class="muted">${esc(d.category)}</div></td><td>${esc(d.metadata?.document_type||'')}</td><td>${fmtDate(d.metadata?.deadline||d.metadata?.warranty_until)}</td><td>${esc(d.profile||'Home')}</td><td>${esc(d.case_name||'—')}</td><td>${esc(d.action_required||'—')}</td><td>${d.health_score}/100</td><td><button class="secondary revealDoc" data-path="${esc(d.path)}">Open</button> <button class="secondary redactDoc" data-id="${d.id}">Redact copy</button></td></tr>`).join('')}</tbody></table></div>`:'<p class="muted">No indexed documents yet.</p>';$$('.revealDoc').forEach(b=>b.addEventListener('click',()=>reveal(b.dataset.path)));$$('.redactDoc').forEach(b=>b.addEventListener('click',async()=>{try{const r=await api(`/api/redact/${b.dataset.id}`,{method:'POST'});alert(`Redacted copy created:\n${r.path}\n\nReview it before sharing.`);reveal(r.path)}catch(e){alert(e.message)}}))}
$('#refreshDocsBtn').addEventListener('click',()=>runLoad(loadDocuments));
async function loadDeadlines(){const d=await api('/api/dashboard');$('#deadlineList').innerHTML=d.deadlines.length?d.deadlines.map(x=>`<div class="listItem"><div class="listItemHead"><strong>${esc(x.name)}</strong><span class="badge ${x.days<0?'red':x.days<=3?'warn':''}">${x.days<0?`${Math.abs(x.days)}d overdue`:x.days===0?'today':`${x.days}d`}</span></div><div class="meta"><span>${fmtDate(x.date)}</span><span>${esc(x.action||'deadline')}</span></div></div>`).join(''):'<p class="muted">No deadlines detected.</p>'}
async function compareDuplicatePair(leftId,rightId){
  const out=$('#duplicateCompareOutput');
  out.classList.remove('hidden');
  out.textContent='Comparing documents…';
  try{
    const r=await api('/api/duplicates/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({left_id:leftId,right_id:rightId})});
    out.textContent=r.exact_hash_match?'SHA-256 match: these files are byte-for-byte identical.':`Similarity: ${(r.similarity*100).toFixed(1)}%\nAdded lines: ${r.added_lines}\nRemoved lines: ${r.removed_lines}\n\n${r.diff||'No text differences detected.'}`;
  }catch(e){out.textContent=e.message}
}
async function loadDuplicates(){
  const groups=await api('/api/duplicates');
  const out=$('#duplicateCompareOutput');
  out.classList.add('hidden');out.textContent='';
  $('#duplicateList').innerHTML=groups.length?groups.map((g,i)=>`<div class="listItem">
    <div class="listItemHead"><strong>${g.kind==='exact'?'Exact duplicates':'Near duplicates'}</strong><span>${g.documents.length} files</span></div>
    ${g.documents.map(d=>`<div class="duplicateRow"><div><strong>${esc(d.source_name)}</strong><div class="muted">${esc(d.path)}</div></div><button class="secondary duplicateOpen" data-path="${esc(d.path)}">Show file</button></div>`).join('')}
    ${g.documents.length>=2?`<div class="actions"><button class="secondary duplicateCompare" data-left="${g.documents[0].id}" data-right="${g.documents[1].id}">${g.kind==='exact'?'Verify first two':'Compare first two'}</button></div>`:''}
  </div>`).join(''):'<p class="muted">No duplicate groups detected.</p>';
  $$('.duplicateOpen').forEach(b=>b.addEventListener('click',()=>reveal(b.dataset.path)));
  $$('.duplicateCompare').forEach(b=>b.addEventListener('click',()=>compareDuplicatePair(Number(b.dataset.left),Number(b.dataset.right))));
}
$('#scanDuplicatesBtn').addEventListener('click',()=>runLoad(loadDuplicates));
async function loadCases(){const cs=await api('/api/cases');$('#caseList').innerHTML=cs.length?cs.map(c=>`<div class="listItem"><h3>${esc(c.name)}</h3>${c.timeline.map(t=>`<div class="meta"><strong>${esc(t.date||'')}</strong><span>${esc(t.name)}</span><span>${esc(t.action||'')}</span>${t.deadline?`<span>deadline ${fmtDate(t.deadline)}</span>`:''}</div>`).join('')}</div>`).join(''):'<p class="muted">Assign documents to cases to build timelines.</p>'}

async function runSearch(){
  const q=$('#searchInput').value.trim();
  if(!q)return;
  const out=$('#searchResults'), btn=$('#searchBtn');
  btn.disabled=true;
  out.innerHTML='<p class="muted">Searching local documents…</p>';
  try{
    const r=await api(`/api/search?q=${encodeURIComponent(q)}`);
    out.innerHTML=r.length?r.map(d=>{
      const text=String(d.extracted_text||'').replace(/\s+/g,' ').trim();
      const snippet=text.slice(0,220);
      return `<div class="listItem">
        <div class="listItemHead"><strong>${esc(d.source_name)}</strong>${d.path?`<button class="secondary searchOpen" data-path="${esc(d.path)}">Show file</button>`:''}</div>
        <div class="meta"><span>match ${Math.round((d.meaning_score||0)*100)}%</span><span>${esc(d.category||'')}</span><span>${esc(d.case_name||'')}</span></div>
        ${snippet?`<p class="muted resultSnippet">${esc(snippet)}${text.length>220?'…':''}</p>`:''}
      </div>`;
    }).join(''):'<p class="muted">No matching documents found.</p>';
    $$('.searchOpen').forEach(b=>b.addEventListener('click',()=>b.dataset.path&&reveal(b.dataset.path)));
  }catch(e){
    out.innerHTML=`<p class="dangerText">Search failed: ${esc(e.message)}</p>`;
  }finally{
    btn.disabled=false;
  }
}

async function runQa(){
  const question=$('#qaInput').value.trim();
  if(!question)return;
  const out=$('#qaAnswer'), btn=$('#qaBtn');
  btn.disabled=true;
  out.innerHTML='<p class="muted">Checking your local index…</p>';
  try{
    const r=await api('/api/qa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});
    const sources=(r.sources||[]).map(s=>`<div class="qaSource">
      <div><strong>${esc(s.name)}</strong><span class="muted"> · match ${Math.round((s.score||0)*100)}%</span></div>
      ${s.path?`<button class="secondary qaOpen" data-path="${esc(s.path)}">Show source</button>`:''}
    </div>`).join('');
    out.innerHTML=`<div class="listItem">
      <strong class="qaAnswerText">${esc(r.answer)}</strong>
      ${sources?`<div class="qaSources"><p class="muted">Source documents</p>${sources}</div>`:''}
    </div>`;
    $$('.qaOpen').forEach(b=>b.addEventListener('click',()=>b.dataset.path&&reveal(b.dataset.path)));
  }catch(e){
    out.innerHTML=`<p class="dangerText">Could not answer: ${esc(e.message)}</p>`;
  }finally{
    btn.disabled=false;
  }
}

$('#searchBtn').addEventListener('click',runSearch);
$('#qaBtn').addEventListener('click',runQa);
$('#searchInput').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();runSearch()}});
$('#qaInput').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();runQa()}});

$('#diffBtn').addEventListener('click',async()=>{try{const r=await api('/api/diff/select',{method:'POST'});if(r.cancelled)return;$('#diffOutput').textContent=`Similarity: ${(r.similarity*100).toFixed(1)}%\nAdded lines: ${r.added_lines}\nRemoved lines: ${r.removed_lines}\n\n${r.diff}`;}catch(e){alert(e.message)}});
$('#scanCleanBtn')?.addEventListener('click',async()=>{try{$('#scanCleanOutput').innerHTML='<p class="muted">Cleaning scan…</p>';const r=await api('/api/scan/clean-select',{method:'POST'});if(r.cancelled){$('#scanCleanOutput').innerHTML='';return}$('#scanCleanOutput').innerHTML=`<p><strong>Clean copy created</strong></p><p class="muted">Quality ${r.quality.score}/100 · ${esc((r.notes||[]).join(' · '))}</p><button class="secondary" id="openCleanScan">Show in Explorer</button>`;$('#openCleanScan').addEventListener('click',()=>reveal(r.path));}catch(e){alert(e.message)}});
$('#batchBtn').addEventListener('click',async()=>{try{$('#batchOutput').innerHTML='<p class="muted">Indexing…</p>';const r=await api('/api/batch/select-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:100})});if(r.cancelled){$('#batchOutput').innerHTML='';return}$('#batchOutput').innerHTML=`<p><strong>${r.indexed}</strong> documents indexed from ${esc(r.folder)}</p>${r.errors.length?`<p class="dangerText">${r.errors.length} errors</p>`:''}`;}catch(e){alert(e.message)}});
$('#emailImportBtn').addEventListener('click',async()=>{try{$('#emailOutput').innerHTML='<p class="muted">Importing…</p>';const r=await api('/api/email/import-eml',{method:'POST'});if(r.cancelled){$('#emailOutput').innerHTML='';return}$('#emailOutput').innerHTML=`<p><strong>${r.attachments.length}</strong> attachments imported from ${esc(r.subject||'email')}</p>`;}catch(e){alert(e.message)}});

$('#watchBtn').addEventListener('click',async()=>{try{const r=await api('/api/watch/select-folder',{method:'POST'});if(!r.cancelled)loadWatch()}catch(e){alert(e.message)}});async function loadWatch(){const r=await api('/api/watch');$('#watchStatus').textContent=r.watch_folder?`Watching: ${r.watch_folder} · ${r.active?'active':'starting'}`:'No watched folder configured.'}
async function loadRules(){const r=await api('/api/rules');$('#rulesList').innerHTML=r.length?r.map(x=>`<div class="listItem"><strong>${esc(x.name)}</strong><div class="meta"><span>${esc(JSON.stringify(x.condition))}</span><span>→ ${esc(x.target_category||'')}</span></div></div>`).join(''):'<p class="muted">No rules yet.</p>'}
$('#addRuleBtn').addEventListener('click',async()=>{const p={name:$('#ruleName').value||'Rule',condition:{issuer_contains:$('#ruleIssuer').value||undefined,text_contains:$('#ruleText').value||undefined},target_category:$('#ruleCategory').value||null,target_profile:$('#ruleProfile').value||null,target_tags:[]};try{await api('/api/rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});loadRules()}catch(e){alert(e.message)}});
async function loadTypes(){const r=await api('/api/custom-types');$('#typesList').innerHTML=r.length?r.map(x=>`<div class="listItem"><strong>${esc(x.name)}</strong><div class="meta"><span>${esc(x.keywords.join(', '))}</span><span>→ ${esc(x.category)}</span></div></div>`).join(''):'<p class="muted">No custom types.</p>'}
$('#addTypeBtn').addEventListener('click',async()=>{const p={name:$('#typeName').value.trim(),keywords:$('#typeKeywords').value.split(',').map(x=>x.trim()).filter(Boolean),category:$('#typeCategory').value||'Documents'};try{await api('/api/custom-types',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});loadTypes()}catch(e){alert(e.message)}});
$('#auditBtn').addEventListener('click',async()=>{const r=await api('/api/audit?limit=100');$('#auditList').innerHTML=r.map(x=>`<div class="listItem"><strong>${esc(x.event)}</strong><div class="meta"><span>${esc(x.created_at)}</span><span>${esc(JSON.stringify(x.payload))}</span></div></div>`).join('')});

let diagnosticsCache=null;
async function loadDiagnostics(){
  const out=$('#diagnosticsStatus');
  if(!out)return;
  out.textContent='Loading diagnostics…';
  try{
    const d=await api('/api/diagnostics');
    diagnosticsCache=d;
    out.innerHTML=`<div class="diagGrid"><span><b>Version</b> ${esc(d.version)}</span><span><b>Mode</b> ${d.packaged?'installed/portable':'source'}</span><span><b>Documents</b> ${d.documents}</span><span><b>Database</b> ${esc(d.database)}</span><span><b>Free space</b> ${d.free_space_gb} GB</span><span><b>Data folder</b> ${esc(d.data_root)}</span></div>`;
  }catch(e){out.textContent=e.message}
}
$('#diagRefreshBtn')?.addEventListener('click',loadDiagnostics);
$('#openDataBtn')?.addEventListener('click',async()=>{try{const d=diagnosticsCache||await api('/api/diagnostics');await reveal(d.data_root)}catch(e){alert(e.message)}});
$('#openLogBtn')?.addEventListener('click',async()=>{try{const d=diagnosticsCache||await api('/api/diagnostics');await reveal(d.log_path)}catch(e){alert(e.message)}});
$('#copyDiagBtn')?.addEventListener('click',async()=>{try{const d=diagnosticsCache||await api('/api/diagnostics');await navigator.clipboard.writeText(JSON.stringify(d.safe_report,null,2));alert('Safe diagnostic report copied. It does not include document contents or local paths.')}catch(e){alert(e.message)}});


async function loadNotificationStatus(){
  try{const r=await api('/api/notifications/status');$('#notifyStatus').textContent=r.enabled?`Background notifications enabled · ${r.days_ahead} day(s) ahead`:'Background notifications disabled.';$('#notifyDays').value=r.days_ahead||3;}catch(e){$('#notifyStatus').textContent=e.message}
}
$('#notifyEnableBtn')?.addEventListener('click',async()=>{try{const days=Number($('#notifyDays').value||3);const r=await api('/api/notifications/enable',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({days_ahead:days})});await loadNotificationStatus();alert(`Background notifications enabled. Test notifications shown: ${r.test_notifications}`);}catch(e){alert(e.message)}});
$('#notifyDisableBtn')?.addEventListener('click',async()=>{try{await api('/api/notifications/disable',{method:'POST'});loadNotificationStatus()}catch(e){alert(e.message)}});

async function loadIntegrationStatus(){
  try{const r=await api('/api/integrations/status');
    $('#emailConnectorStatus').textContent=r.email.configured?`${r.email.provider}: ${r.email.email} · ${r.email.secret_available?'credential stored':'credential missing'}`:'Not configured.';
    $('#notionStatus').textContent=r.notion.configured?`Configured · database ${r.notion.database_id}`:'Not configured.';
    $('#googleStatus').textContent=r.google_calendar.configured?`OAuth client selected · ${r.google_calendar.authorized?'authorized':'authorization will open on first sync'}`:'Not configured.';
  }catch(e){console.warn(e)}
}
$('#emailConfigureBtn')?.addEventListener('click',async()=>{try{await api('/api/integrations/email',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:$('#emailProvider').value,email:$('#emailAddress').value,password:$('#emailPassword').value,folder:$('#emailFolder').value||'INBOX'})});$('#emailPassword').value='';loadIntegrationStatus()}catch(e){alert(e.message)}});
$('#emailImapImportBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/email/import-imap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({unread_only:true,max_messages:20})});alert(`Imported ${r.attachments.length} attachment(s).`);loadDashboard()}catch(e){alert(e.message)}});
$('#notionConfigureBtn')?.addEventListener('click',async()=>{try{await api('/api/integrations/notion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:$('#notionToken').value,database_id:$('#notionDatabase').value})});$('#notionToken').value='';loadIntegrationStatus()}catch(e){alert(e.message)}});
$('#notionSyncBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/integrations/notion/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:100})});alert(`Notion sync: ${r.synced} document(s).${r.errors?.length?` ${r.errors.length} error(s).`:''}`)}catch(e){alert(e.message)}});
$('#googleClientBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/integrations/google-calendar/select-client',{method:'POST'});if(!r.cancelled)loadIntegrationStatus()}catch(e){alert(e.message)}});
$('#googleSyncBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/integrations/google-calendar/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({calendar_id:'primary'})});alert(`Google Calendar sync: ${r.synced} deadline(s).${r.errors?.length?` ${r.errors.length} error(s).`:''}`);loadIntegrationStatus()}catch(e){alert(e.message)}});

$('#changesBtn').addEventListener('click',async()=>{
  const r=await api('/api/changes');
  $('#changesList').innerHTML=r.length?r.map(x=>`<div class="listItem"><strong>${esc(x.action)}: ${esc(x.destination)}</strong><div class="meta"><span>${esc(x.created_at)}</span></div><button class="secondary historyUndo" data-id="${x.id}">Undo</button></div>`).join(''):'<p class="muted">No reversible changes.</p>';
  $$('.historyUndo').forEach(b=>b.addEventListener('click',async()=>{try{const u=await api(`/api/undo/${b.dataset.id}`,{method:'POST'});alert(`Restored to:\n${u.restored_to}`);$('#changesBtn').click()}catch(e){alert(e.message)}}));
});

loadSetupStatus().finally(()=>runLoad(loadDashboard));
