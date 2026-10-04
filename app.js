const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let current = null, currentChange = null, pickerBusy = false, deferredInstallPrompt = null, setupState = null, editingRuleId = null, selectedDocumentIds = new Set(), documentsPageOffset = 0, documentsPageTotal = 0, documentsFilterValue = '', pendingPortableConfig = null, lifePilotItems = [], lifePilotFilter = 'active';
const documentsPageLimit = 100;
const titles = {
  dashboard:['LifeAdmin','Jedna aplikacja do ogarniania dorosłego życia.'], lifepilot:['LifePilot · Co teraz?','Priorytetowa kolejka następnych działań'], inbox:['Wrzuć dokument','LifeAdmin układa, LifePilot podpowiada co dalej'], review:['Review Queue','Documents that need a human decision'],
  documents:['Documents','Your local document index'], deadlines:['Deadline Radar','Payments, replies, expirations and warranties'],
  duplicates:['Duplicates','Exact and near-duplicate detection'], cases:['Cases & Timeline','Group related documents into one story'],
  search:['Search & Q&A','Search locally by meaning and ask factual questions'], tools:['Tools','Diff, batch import, redaction and document health'],
  automation:['Automation','Watch folders, rules, profiles and custom types'], exports:['Exports','Calendar, Obsidian, Notion and backup'],
  settings:['Settings','Data, diagnostics, privacy and integrations']
};

function esc(v=''){return String(v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function fmtDate(v){if(!v)return '—'; try{return new Date(v+'T00:00:00').toLocaleDateString();}catch{return v}}
function fmtDateTime(v){if(!v)return '—';try{return new Date(v).toLocaleString()}catch{return v}}
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

$$('.navBtn').forEach(b=>b.addEventListener('click',()=>go(b.dataset.view)));
$$('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go)));
$('#nav')?.addEventListener('keydown',e=>{
  if(!['ArrowDown','ArrowUp','ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;
  const items=$$('.navBtn');
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
  $$('.navBtn').forEach(b=>{
    const active=b.dataset.view===name;
    b.classList.toggle('active',active);
    if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');
  });
  $$('.view').forEach(v=>v.classList.remove('activeView'));
  target.classList.add('activeView');
  $('#viewTitle').textContent=titles[name][0];
  $('#viewSubtitle').textContent=titles[name][1];
  if(focus)requestAnimationFrame(()=>$('#viewTitle')?.focus({preventScroll:true}));
  if(name==='dashboard')runLoad(loadDashboard);
  if(name==='lifepilot')runLoad(loadLifePilot);
  if(name==='review')runLoad(loadReview);
  if(name==='documents')runLoad(loadDocuments);
  if(name==='deadlines')runLoad(loadDeadlines);
  if(name==='duplicates')runLoad(loadDuplicates);
  if(name==='cases')runLoad(loadCases);
  if(name==='automation'){runLoad(loadRules);runLoad(loadTypes);runLoad(loadWatch)}
  if(name==='settings'){runLoad(loadIntegrationStatus);runLoad(loadIntegrationHistory);runLoad(loadNotificationStatus);runLoad(loadDiagnostics);runLoad(loadRecoveryPoints);runLoad(loadRuntimeStatus)}
}

window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredInstallPrompt=e;$('#installPwaBtn').classList.remove('hidden')});
async function installPwa(){if(!deferredInstallPrompt){showAppNotice('Use your browser menu and choose Install app / Install DocPilot if the install option is available.','ok');return}deferredInstallPrompt.prompt();await deferredInstallPrompt.userChoice;deferredInstallPrompt=null;}
$('#installPwaBtn').addEventListener('click',installPwa);$('#installPwaBtn2').addEventListener('click',installPwa);
if('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(()=>{});

function clientRuntimeMode(){
  const params=new URLSearchParams(window.location.search);
  if(params.get('client')==='desktop')return 'Desktop';
  if(window.matchMedia?.('(display-mode: standalone)').matches||window.navigator.standalone===true)return 'Installed PWA';
  return 'Browser';
}

async function serviceWorkerShellInfo(){
  if(!('serviceWorker' in navigator))return {supported:false,version:null,cache:null};
  try{
    const registration=await navigator.serviceWorker.ready;
    const worker=registration.active||registration.waiting||registration.installing;
    if(!worker)return {supported:true,version:null,cache:null};
    return await new Promise(resolve=>{
      const channel=new MessageChannel();
      const timer=setTimeout(()=>resolve({supported:true,version:null,cache:null}),1200);
      channel.port1.onmessage=event=>{
        clearTimeout(timer);
        resolve({supported:true,version:event.data?.version||null,cache:event.data?.cache||null});
      };
      worker.postMessage({type:'DOC_PILOT_VERSION'},[channel.port2]);
    });
  }catch{
    return {supported:true,version:null,cache:null};
  }
}

async function refreshPwaShell(){
  if(!('serviceWorker' in navigator)){
    showAppNotice('Service workers are not supported in this client.');
    return;
  }

  const button=$('#runtimeUpdateShellBtn');
  if(button){button.disabled=true;button.textContent='Updating…'}
  try{
    const registration=await navigator.serviceWorker.getRegistration()||await navigator.serviceWorker.ready;
    let changed=false;
    const controllerChanged=new Promise(resolve=>{
      const timer=setTimeout(resolve,4500);
      navigator.serviceWorker.addEventListener('controllerchange',()=>{
        changed=true;
        clearTimeout(timer);
        resolve();
      },{once:true});
    });

    await registration.update();
    if(registration.waiting)registration.waiting.postMessage({type:'SKIP_WAITING'});
    await controllerChanged;
    showAppNotice(changed?'Updated PWA shell. Reloading…':'PWA update checked. Reloading…','ok');
    window.location.reload();
  }catch(e){
    showAppNotice(e.message);
    if(button){button.disabled=false;button.textContent='Update PWA shell'}
  }
}

async function loadRuntimeStatus(){
  const target=$('#runtimeStatus');
  if(!target)return;
  target.textContent='Checking runtime…';
  try{
    const [health,shell]=await Promise.all([api('/api/health'),serviceWorkerShellInfo()]);
    const mode=clientRuntimeMode();
    const shellVersion=shell.version||'unavailable';
    const mismatch=Boolean(shell.version&&shell.version!==health.version);
    target.innerHTML=`<div class="diagGrid"><span><b>Client</b> ${esc(mode)}</span><span><b>Backend</b> v${esc(health.version)}</span><span><b>PWA shell</b> ${esc(shellVersion)}</span><span><b>Service worker</b> ${shell.supported?'supported':'not supported'}</span></div>${mismatch?'<p class="dangerText"><strong>Version mismatch:</strong> the cached PWA shell does not match the local backend.</p><button id="runtimeUpdateShellBtn" class="secondary">Update PWA shell</button>':'<p class="muted">Desktop, browser and installed PWA use the same local backend. The backend must be running for document operations.</p>'}`;
    $('#runtimeUpdateShellBtn')?.addEventListener('click',refreshPwaShell);
  }catch(e){
    target.innerHTML=`<p class="dangerText">Local backend unavailable: ${esc(e.message)}</p><p class="muted">Start DocPilot on this PC, then reload the browser or PWA window.</p>`;
  }
}

async function api(url,opts={}){const r=await fetch(url,{cache:'no-store',...opts});if(!r.ok){let detail='';try{const j=await r.json();detail=j.detail||''}catch{}const err=new Error(friendlyApiMessage(r.status,detail));err.status=r.status;throw err}return r.headers.get('content-type')?.includes('application/json')?r.json():r.text()}

function lifePilotVisibleItems(){
  return lifePilotItems.filter(item=>{
    const priority=item.next_action?.priority||'normal';
    if(lifePilotFilter==='done')return item.done===true;
    if(item.done)return false;
    if(lifePilotFilter==='today')return priority==='overdue'||priority==='today';
    if(lifePilotFilter==='urgent')return ['overdue','today','urgent'].includes(priority);
    if(lifePilotFilter==='review')return priority==='review';
    if(lifePilotFilter==='soon')return priority==='soon';
    return true;
  });
}

function renderLifePilot(){
  const target=$('#lifepilotQueue'), stats=$('#lifeQueueStats');
  if(!target)return;
  const active=lifePilotItems.filter(x=>!x.done);
  const counts={
    overdue:active.filter(x=>x.next_action?.priority==='overdue').length,
    today:active.filter(x=>x.next_action?.priority==='today').length,
    urgent:active.filter(x=>x.next_action?.priority==='urgent').length,
    review:active.filter(x=>x.next_action?.priority==='review').length,
    done:lifePilotItems.filter(x=>x.done).length
  };
  if(stats)stats.innerHTML=[
    ['Aktywne',active.length],['Po terminie',counts.overdue],['Dzisiaj',counts.today],
    ['Pilne',counts.urgent],['Do sprawdzenia',counts.review],['Załatwione',counts.done]
  ].map(([label,value])=>`<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join('');
  const items=lifePilotVisibleItems();
  if(!items.length){
    target.innerHTML='<p class="muted">Brak pozycji w tym widoku.</p>';
    return;
  }
  target.innerHTML=items.map(item=>{
    const next=item.next_action||{};
    const badge=next.priority==='overdue'?'red':(next.priority==='urgent'||next.priority==='today'||next.priority==='review')?'warn':'';
    const stateBadge=item.done?'<span class="badge">ZAŁATWIONE</span>':'';
    const actionButton=item.done
      ?`<button class="secondary lifeReopen" data-id="${item.id}">Przywróć do kolejki</button>`
      :`<button class="secondary lifeDone" data-id="${item.id}">Oznacz jako załatwione</button>`;
    const verification=next.verification||{};
    const verificationBadge=verification.source==='manual'
      ? '<span class="badge">DANE SPRAWDZONE</span>'
      : `<span class="badge">AUTO ${Math.round(Number(verification.confidence||0)*100)}%</span>`;
    const doneMeta=item.done&&item.done_at?`<span>Załatwione: ${fmtDateTime(item.done_at)}</span>`:'';
    const decision=(next.decision_basis||[]).length?`<details class="lifeDecision"><summary>Dlaczego LifePilot tak zaleca?</summary><ul>${next.decision_basis.map(reason=>`<li>${esc(reason)}</li>`).join('')}</ul></details>`:'';
    return `<div class="lifeQueueItem ${item.done?'lifeQueueDone':''}"><div class="listItemHead"><div><span class="badge ${badge}">${esc((next.priority||'normal').toUpperCase())}</span> ${verificationBadge}<h3>${esc(item.source_name||'Dokument')}</h3></div><div class="inline">${stateBadge}<span class="badge ${badge}">${esc(next.title||'Sprawdź dokument')}</span></div></div><p>${esc(next.reason||'')}</p><div class="meta">${item.case_name?`<span>Sprawa: ${esc(item.case_name)}</span>`:''}${item.category?`<span>${esc(item.category)}</span>`:''}${next.due_date?`<span>Termin: ${fmtDate(next.due_date)}</span>`:''}${doneMeta}</div>${decision}<div class="lifePilotActions"><button class="secondary lifeOpenInDocs" data-name="${esc(item.source_name||'')}">Otwórz w Documents</button><button class="secondary lifePreviewProof" data-id="${item.id}">Co będzie w ProofPack?</button><a class="buttonLink" href="/api/lifepilot/${item.id}/proofpack">ProofPack ZIP</a>${next.due_date?`<a class="buttonLink secondary" href="/api/lifepilot/${item.id}/calendar">Termin .ics</a>`:''}${actionButton}</div><div class="proofPackPreview hidden" id="proofPreview-${item.id}"></div></div>`;
  }).join('');
  $$('.lifeOpenInDocs').forEach(button=>button.addEventListener('click',()=>{
    documentsFilterValue=button.dataset.name||'';
    documentsPageOffset=0;
    const input=$('#documentsFilter');
    if(input)input.value=documentsFilterValue;
    go('documents');
  }));
  $$('.lifeDone').forEach(button=>button.addEventListener('click',async()=>{
    if(!confirm('Oznaczyć tę pozycję jako załatwioną? Dokument pozostanie w archiwum i można ją później przywrócić.'))return;
    try{await api(`/api/lifepilot/${button.dataset.id}/done`,{method:'POST'});await loadLifePilot();showAppNotice('Pozycja oznaczona jako załatwiona.','ok')}catch(e){showAppNotice(e.message)}
  }));
  $$('.lifeReopen').forEach(button=>button.addEventListener('click',async()=>{
    try{await api(`/api/lifepilot/${button.dataset.id}/reopen`,{method:'POST'});await loadLifePilot();showAppNotice('Pozycja wróciła do aktywnej kolejki.','ok')}catch(e){showAppNotice(e.message)}
  }));
  $$('.lifePreviewProof').forEach(button=>button.addEventListener('click',async()=>{
    const box=$(`#proofPreview-${button.dataset.id}`);
    if(!box)return;
    if(!box.classList.contains('hidden')){box.classList.add('hidden');return}
    box.classList.remove('hidden');box.innerHTML='<p class="muted">Sprawdzam zawartość pakietu…</p>';
    try{
      const p=await api(`/api/lifepilot/${button.dataset.id}/proofpack-preview`);
      box.innerHTML=`<div class="proofPreviewHead"><strong>ProofPack przed pobraniem</strong><span class="badge">${p.timeline_items} element(y) timeline</span></div><div class="meta"><span>Oryginał: ${p.source_available?'dostępny':'brak'}</span><span>SHA-256: ${p.integrity?.indexed_digest_available?'zapisany':'brak w indeksie'}</span><span>Wysyłka do chmury: nie</span></div><ul>${(p.files||[]).map(file=>`<li>${esc(file.name)} ${file.available?'':'— niedostępny'}</li>`).join('')}</ul><p class="muted">Manifest nie zawiera pełnego OCR ani lokalnej ścieżki dokumentu.</p>`;
    }catch(e){box.innerHTML=`<p class="dangerText">${esc(e.message)}</p>`}
  }));
}

async function loadLifePilot(){
  const target=$('#lifepilotQueue');
  if(!target)return;
  lifePilotItems=await api('/api/lifepilot/queue?limit=250&include_done=true');
  renderLifePilot();
}

$('#refreshLifePilotBtn')?.addEventListener('click',()=>runLoad(loadLifePilot));
document.querySelectorAll('[data-life-filter]').forEach(button=>button.addEventListener('click',()=>{
  lifePilotFilter=button.dataset.lifeFilter||'active';
  document.querySelectorAll('[data-life-filter]').forEach(item=>item.classList.toggle('active',item===button));
  renderLifePilot();
}));

async function loadDashboard(){
  const [d,life]=await Promise.all([api('/api/dashboard'),api('/api/lifeadmin')]);
  const welcome=$('#welcomeCard');
  const setupActive=setupState&&!setupState.complete&&!setupState.has_documents;
  if(welcome)welcome.classList.toggle('hidden',d.documents>0||setupActive);
  $('#stats').innerHTML=[
    ['Dokumenty',d.documents],['Terminy',d.deadline_count],['Do zrobienia',d.actions],
    ['Po terminie',life.overdue],['Sprawy',d.cases],['Alerty jakości',d.unhealthy]
  ].map(([a,b])=>`<div class="stat"><strong>${b}</strong><span>${a}</span></div>`).join('');
  const areaGrid=$('#lifeAreaGrid');
  if(areaGrid)areaGrid.innerHTML=(life.areas||[]).map(a=>`<article class="lifeAreaCard">
    <div class="lifeAreaTop"><span class="lifeAreaIcon">${esc(a.icon)}</span><div><strong>${esc(a.label)}</strong><small>${a.count} dokumentów</small></div></div>
    <div class="lifeAreaMeta"><span>${a.open_actions} do zrobienia</span><span class="${a.overdue?'dangerText':''}">${a.overdue} po terminie</span></div>
    <div class="muted">${a.next_date?`Najbliższy termin: ${fmtDate(a.next_date)}`:'Brak wykrytego terminu'}</div>
  </article>`).join('');
  $('#dashboardDeadlines').innerHTML=(life.timeline||[]).length?(life.timeline||[]).slice(0,8).map(x=>`<div class="listItem"><div class="listItemHead"><strong>${esc(x.name)}</strong><span class="badge ${x.days<0?'red':x.days<=3?'warn':''}">${x.days<0?`${Math.abs(x.days)}d po terminie`:x.days===0?'dzisiaj':`${x.days}d`}</span></div><div class="meta"><span>${esc(x.area_label)} · ${esc(x.event)}</span><span>${fmtDate(x.date)}</span></div><div class="muted">${esc(x.action||'Sprawdź termin')}</div></div>`).join(''):'<p class="muted">Brak wykrytych terminów.</p>';
  $('#dashboardActions').innerHTML=d.actions?`<div class="stat"><strong>${d.actions}</strong><span>spraw wymaga działania</span></div><p class="muted">LifePilot układa je w kolejności „Co teraz?”.</p>`:'<p class="muted">Na razie nic nie wymaga działania.</p>';
  $('#featureGrid').innerHTML=[['LifeAdmin','obszary dorosłego życia'],['LifePilot','jedna jasna następna akcja'],['Powiadomienia','priorytety LifePilot w tle'],['ProofPack','oryginał + oś czasu + SHA-256'],['OCR','lokalny OCR PL/EN'],['Terminy','płatność, ważność, gwarancja'],['Archiwum','silnik DocPilot'],['Search','lokalne Q&A']].map(([a,b])=>`<div class="feature"><strong>${a}</strong><small>${b}</small></div>`).join('');
}

const drop=$('#dropZone'), browse=$('#browseBtn');browse.addEventListener('click',selectLocalFile);['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>{const f=e.dataTransfer.files[0];if(f)analyzeCopy(f)});
async function selectLocalFile(){if(pickerBusy)return;pickerBusy=true;browse.disabled=true;browse.textContent='Opening Windows picker…';try{const d=await api('/api/select-local',{method:'POST'});if(!d.cancelled){current=d;showAnalysis(d)}}catch(e){showAppNotice(e.message)}finally{pickerBusy=false;browse.disabled=false;browse.textContent='Select file on this PC'}}
async function analyzeCopy(file){const fd=new FormData();fd.append('upload',file);try{const d=await api('/api/analyze',{method:'POST',body:fd});current=d;showAnalysis(d)}catch(e){showAppNotice(e.message)}}
function lifePilotCorrectionPayload(){
  const rawAmount=$('#lifeAmount')?.value?.trim()||'';
  const amount=rawAmount===''?null:Number(rawAmount);
  if(rawAmount!==''&&!Number.isFinite(amount))throw new Error('Kwota musi być liczbą.');
  return {
    document_type:$('#docType')?.value?.trim()||'document',
    issuer:$('#lifeIssuer')?.value?.trim()||null,
    amount,
    currency:$('#lifeCurrency')?.value?.trim().toUpperCase()||null,
    document_date:$('#lifeDocumentDate')?.value||null,
    deadline:$('#lifeDeadline')?.value||null,
    warranty_until:$('#lifeWarrantyUntil')?.value||null,
    case_name:$('#caseName')?.value?.trim()||null,
    action_required:$('#actionRequired')?.value||null
  };
}

function lifePilotCorrectionsDirty(){
  if(!current)return false;
  const md=current.metadata||{};
  let payload;
  try{payload=lifePilotCorrectionPayload()}catch{return true}
  const normalize=value=>value==null||value===''?null:String(value);
  const currentAmount=md.amount==null?null:Number(md.amount);
  return (
    normalize(payload.document_type)!==normalize(md.document_type||'document')||
    normalize(payload.issuer)!==normalize(md.issuer)||
    payload.amount!==currentAmount||
    normalize(payload.currency)!==normalize(md.currency)||
    normalize(payload.document_date)!==normalize(md.document_date)||
    normalize(payload.deadline)!==normalize(md.deadline)||
    normalize(payload.warranty_until)!==normalize(md.warranty_until)||
    normalize(payload.case_name)!==normalize(current.suggested_case)||
    normalize(payload.action_required)!==normalize(current.action_required)
  );
}

async function saveLifePilotCorrections({quiet=false}={}){
  if(!current?.id)return;
  const payload=lifePilotCorrectionPayload();
  const updated=await api(`/api/lifepilot/${current.id}/fields`,{
    method:'PATCH',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload)
  });
  current={
    ...current,
    metadata:updated.metadata||current.metadata,
    suggested_case:updated.case_name,
    action_required:updated.action_required,
    suggested_category:updated.category||current.suggested_category,
    profile:updated.profile||current.profile,
    lifepilot:updated.lifepilot||current.lifepilot
  };
  showAnalysis(current);
  if(!quiet)showAppNotice('Sprawdzone dane zapisane. LifePilot przeliczył „Co teraz?”.','ok');
}

function showAnalysis(d){
  drop.classList.add('hidden');
  $('#successPanel').classList.add('hidden');
  const md=d.metadata||{};
  const sensitive=(d.sensitive||[]).map(x=>`${x.type}: ${x.value}`).join(' · ');
  const matchedRules=(d.matched_rules||[]).map(x=>x.name||'Rule').join(' · ');
  const lp=d.lifepilot||{},next=lp.next_action||{};
  const lpBadge=next.priority==='overdue'?'red':(next.priority==='urgent'||next.priority==='today'||next.priority==='review')?'warn':'';
  const verified=md.manual_verified?'<span class="badge">DANE SPRAWDZONE RĘCZNIE</span>':'';
  const verification=next.verification||{};
  const verificationLine=verification.source==='manual'
    ? `<div class="meta"><span>Dane sprawdzone ręcznie${verification.verified_at?` · ${fmtDateTime(verification.verified_at)}`:''}</span></div>`
    : `<div class="meta"><span>Automatyczny odczyt · ${Math.round(Number(verification.confidence||0)*100)}% pewności</span></div>`;
  const decision=(next.decision_basis||[]).length?`<details class="lifeDecision"><summary>Dlaczego LifePilot tak zaleca?</summary><ul>${next.decision_basis.map(reason=>`<li>${esc(reason)}</li>`).join('')}</ul></details>`:'';
  const areaNames={car:'Samochód',home:'Dom',children:'Dzieci',shopping:'Zakupy',documents:'Dokumenty'};
  const lifeAdminCard=`<div class="lifeResult"><div><small>Obszar życia</small><strong>${esc(areaNames[md.life_area]||'Dokumenty')}</strong></div><div><small>Sprawa</small><strong>${esc(md.life_event||md.document_type||'dokument')}</strong></div><div><small>Następna akcja</small><strong>${esc(md.life_action||next.title||'Sprawdź dokument')}</strong></div><div><small>Termin</small><strong>${esc(md.reminder_date||md.deadline||md.warranty_until||'brak')}</strong></div></div>`;
  const lifeCard=next.title?`<div class="lifePilotCard"><div class="listItemHead"><div><span class="badge">LIFEPILOT · CO TERAZ?</span><h3>${esc(next.title)}</h3></div><span class="badge ${lpBadge}">${esc(next.priority||'normal')}</span></div><p>${esc(next.reason||'')}</p>${verificationLine}${next.due_date?`<div class="meta"><span>Termin: ${fmtDate(next.due_date)}</span></div>`:''}${(next.steps||[]).length?`<div class="meta"><span>${esc(next.steps.join(' · '))}</span></div>`:''}${decision}<div class="lifePilotActions"><a class="buttonLink" href="/api/lifepilot/${d.id}/proofpack">Pobierz ProofPack ZIP</a>${next.due_date?`<a class="buttonLink secondary" href="/api/lifepilot/${d.id}/calendar">Dodaj termin (.ics)</a>`:''}<button class="secondary" id="lifeOpenSource">Otwórz dokument</button><a class="buttonLink secondary" href="https://lukaszst-cz.github.io/czy-to-sciema/" target="_blank" rel="noopener">Sprawdź jako ściemę ↗</a><a class="buttonLink secondary" href="/lifepilot" target="_blank" rel="noopener">O LifePilot</a></div><p class="muted lifePilotPrivacy">CzyToŚciema? otwiera się osobno. LifePilot nie wysyła tam automatycznie treści dokumentu.</p></div>`:'' ;
  $('#analysisPanel').classList.remove('hidden');
  $('#analysisPanel').innerHTML=`<div class="cardHead"><div><span class="badge">ANALYZED</span> ${verified}<h2>${esc(d.source_name)}</h2></div><span>${Math.round((md.confidence||0)*100)}% confidence</span></div><div class="modeNotice ${d.source_mode==='original'?'original':'copy'}">${d.source_mode==='original'?'REAL FILE MODE — Apply can rename or move the original.':'COPY MODE — drag & drop imported a safe copy.'}</div><div class="sourcePath">${esc(d.source_path)}</div>${matchedRules?`<div class="meta"><span>Matched rules: ${esc(matchedRules)}</span></div>`:'' }${lifeAdminCard}${lifeCard}<div class="lifeCorrectionIntro"><strong>Sprawdź kluczowe dane</strong><p class="muted">Te pola wpływają na rekomendację LifePilot. Popraw je na podstawie oryginału i zapisz.</p></div><div class="grid"><label>Type<input id="docType" value="${esc(md.document_type||'document')}"></label><label>Issuer<input id="lifeIssuer" value="${esc(md.issuer||'')}"></label><label>Amount<input id="lifeAmount" inputmode="decimal" value="${md.amount==null?'':esc(md.amount)}"></label><label>Currency<input id="lifeCurrency" maxlength="3" value="${esc(md.currency||'')}"></label><label>Document date<input id="lifeDocumentDate" type="date" value="${esc(md.document_date||'')}"></label><label>Deadline<input id="lifeDeadline" type="date" value="${esc(md.deadline||'')}"></label><label>Warranty until<input id="lifeWarrantyUntil" type="date" value="${esc(md.warranty_until||'')}"></label><label>Language<input value="${esc(md.language||'unknown')}" disabled></label><label>Health<input value="${d.health_score}/100" disabled></label><label class="wide">Category<input id="category" value="${esc(d.suggested_category)}"></label><label class="wide">Suggested filename<input id="suggestedFilename" value="${esc(d.suggested_filename)}"></label><label>Profile<select id="profile"><option>Home</option><option>Company</option><option>Child</option><option>Vehicle</option><option>Legal Cases</option></select></label><label>Action<select id="actionRequired"><option value="">None</option><option value="to-pay">To pay</option><option value="to-reply">To reply</option><option value="to-sign">To sign</option><option value="to-review">To review</option><option value="to-renew">To renew</option><option value="to-archive">To archive</option></select></label><label class="wide">Case<input id="caseName" value="${esc(d.suggested_case||'')}"></label><label class="wide">Apply action<select id="applyMode"><option value="rename">Rename original in the same folder</option><option value="organize">Move + rename into DocPilot archive</option></select></label><label class="wide"><input id="smartStructure" type="checkbox" checked style="width:auto;margin-right:8px"> Smart folder structure (category / year / issuer) when organizing</label></div><div class="actions lifeVerifyActions"><button class="secondary" id="saveLifeFields">Zapisz sprawdzone dane</button></div>${sensitive?`<p class="badge warn">Sensitive data detected</p><p class="muted">${esc(sensitive)}</p>`:''}${(d.health_notes||[]).length?`<p class="muted">Health: ${esc(d.health_notes.join(' · '))}</p>`:''}<div class="actions"><button class="secondary" id="cancelAnalyze">Analyze another</button><button id="applyBtn">Apply</button></div>`;
  $('#profile').value=d.profile||'Home';
  $('#actionRequired').value=d.action_required||'';
  if(d.source_mode!=='original'){$('#applyMode').value='organize';$('#applyMode').disabled=true}
  $('#cancelAnalyze').addEventListener('click',resetInbox);
  $('#applyBtn').addEventListener('click',applyCurrent);
  $('#saveLifeFields').addEventListener('click',async()=>{
    const button=$('#saveLifeFields');button.disabled=true;button.textContent='Zapisuję…';
    try{await saveLifePilotCorrections()}catch(e){showAppNotice(e.message);button.disabled=false;button.textContent='Zapisz sprawdzone dane'}
  });
  $('#lifeOpenSource')?.addEventListener('click',async()=>{try{await api('/api/open-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:d.source_path})})}catch(e){showAppNotice(e.message)}})
}
function resetInbox(){current=null;currentChange=null;$('#analysisPanel').classList.add('hidden');$('#successPanel').classList.add('hidden');drop.classList.remove('hidden')}
async function applyCurrent(){
  if(lifePilotCorrectionsDirty()){
    try{await saveLifePilotCorrections({quiet:true})}
    catch(e){showAppNotice(e.message);return}
  }
  const mode=$('#applyMode').value;
  const verifiedMetadata=current.metadata?.manual_verified?{
    document_type:current.metadata.document_type,
    issuer:current.metadata.issuer,
    amount:current.metadata.amount,
    currency:current.metadata.currency,
    document_date:current.metadata.document_date,
    deadline:current.metadata.deadline,
    warranty_until:current.metadata.warranty_until
  }:{};
  const p={source_path:current.source_path,category:$('#category').value,filename:$('#suggestedFilename').value,mode,profile:$('#profile').value,case_name:$('#caseName').value||null,action_required:$('#actionRequired').value||null,smart_structure:$('#smartStructure')?.checked!==false,metadata_overrides:verifiedMetadata};

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

function updateBulkDocumentsBar(){
  const bar=$('#bulkDocumentsBar');
  if(!bar)return;
  $('#bulkSelectedCount').textContent=selectedDocumentIds.size;
  bar.classList.toggle('hidden',selectedDocumentIds.size===0);
  const mode=$('#bulkCaseMode').value;
  $('#bulkCaseName').disabled=mode!=='set';
}

function documentsPageUrl(){
  const params=new URLSearchParams({limit:String(documentsPageLimit),offset:String(documentsPageOffset)});
  if(documentsFilterValue)params.set('q',documentsFilterValue);
  return `/api/documents/page?${params.toString()}`;
}

async function loadDocuments(){
  const page=await api(documentsPageUrl());
  const docs=page.items||[];
  documentsPageTotal=Number(page.total||0);

  if(!docs.length&&documentsPageOffset>0&&documentsPageTotal>0){
    documentsPageOffset=Math.max(0,Math.floor((documentsPageTotal-1)/documentsPageLimit)*documentsPageLimit);
    return loadDocuments();
  }

  const visibleIds=new Set(docs.map(d=>Number(d.id)));
  selectedDocumentIds=new Set([...selectedDocumentIds].filter(id=>visibleIds.has(id)));

  const startIndex=documentsPageTotal?documentsPageOffset+1:0;
  const endIndex=Math.min(documentsPageOffset+docs.length,documentsPageTotal);
  $('#documentsPageInfo').textContent=`${startIndex}–${endIndex} of ${documentsPageTotal}`;
  $('#prevDocumentsPage').disabled=documentsPageOffset<=0;
  $('#nextDocumentsPage').disabled=!page.has_more;

  $('#documentsTable').innerHTML=docs.length?`<div class="tableWrap"><table><thead><tr><th><input type="checkbox" id="selectAllDocs" aria-label="Select all visible documents"></th><th>Name</th><th>Type</th><th>Deadline</th><th>Profile</th><th>Case</th><th>Action</th><th>Health</th><th></th></tr></thead><tbody>${docs.map(d=>`<tr><td><input type="checkbox" class="docSelect" data-id="${d.id}" aria-label="Select ${esc(d.source_name)}" ${selectedDocumentIds.has(Number(d.id))?'checked':''}></td><td><strong>${esc(d.source_name)}</strong><div class="muted">${esc(d.category)}</div></td><td>${esc(d.metadata?.document_type||'')}</td><td>${fmtDate(d.metadata?.deadline||d.metadata?.warranty_until)}</td><td>${esc(d.profile||'Home')}</td><td>${esc(d.case_name||'—')}</td><td>${esc(d.action_required||'—')}</td><td>${d.health_score}/100</td><td><button class="secondary revealDoc" data-path="${esc(d.path)}">Open</button> <button class="secondary redactDoc" data-id="${d.id}">Redact copy</button></td></tr>`).join('')}</tbody></table></div>`:'<p class="muted">No matching documents.</p>';

  const all=$('#selectAllDocs');
  if(all){
    all.checked=docs.length>0&&docs.every(d=>selectedDocumentIds.has(Number(d.id)));
    all.addEventListener('change',()=>{
      selectedDocumentIds=all.checked?new Set(docs.map(d=>Number(d.id))):new Set();
      $$('.docSelect').forEach(box=>{box.checked=all.checked});
      updateBulkDocumentsBar();
    });
  }

  $$('.docSelect').forEach(box=>box.addEventListener('change',()=>{
    const id=Number(box.dataset.id);
    if(box.checked)selectedDocumentIds.add(id);else selectedDocumentIds.delete(id);
    if(all)all.checked=docs.length>0&&docs.every(d=>selectedDocumentIds.has(Number(d.id)));
    updateBulkDocumentsBar();
  }));
  $$('.revealDoc').forEach(b=>b.addEventListener('click',()=>reveal(b.dataset.path)));
  $$('.redactDoc').forEach(b=>b.addEventListener('click',async()=>{try{const r=await api(`/api/redact/${b.dataset.id}`,{method:'POST'});showAppNotice(`Redacted copy created: ${r.path}. Review it before sharing.`,'ok');reveal(r.path)}catch(e){showAppNotice(e.message)}}));
  updateBulkDocumentsBar();
}

$('#refreshDocsBtn').addEventListener('click',()=>runLoad(loadDocuments));
$('#applyDocumentsFilter').addEventListener('click',()=>{
  documentsFilterValue=$('#documentsFilter').value.trim();
  documentsPageOffset=0;
  selectedDocumentIds.clear();
  runLoad(loadDocuments);
});
$('#clearDocumentsFilter').addEventListener('click',()=>{
  $('#documentsFilter').value='';
  documentsFilterValue='';
  documentsPageOffset=0;
  selectedDocumentIds.clear();
  runLoad(loadDocuments);
});
$('#documentsFilter').addEventListener('keydown',event=>{
  if(event.key==='Enter')$('#applyDocumentsFilter').click();
});
$('#prevDocumentsPage').addEventListener('click',()=>{
  documentsPageOffset=Math.max(0,documentsPageOffset-documentsPageLimit);
  selectedDocumentIds.clear();
  runLoad(loadDocuments);
});
$('#nextDocumentsPage').addEventListener('click',()=>{
  if(documentsPageOffset+documentsPageLimit>=documentsPageTotal)return;
  documentsPageOffset+=documentsPageLimit;
  selectedDocumentIds.clear();
  runLoad(loadDocuments);
});
$('#bulkCaseMode').addEventListener('change',updateBulkDocumentsBar);
$('#clearBulkDocs').addEventListener('click',()=>{
  selectedDocumentIds.clear();
  $$('.docSelect').forEach(box=>{box.checked=false});
  const all=$('#selectAllDocs');if(all)all.checked=false;
  updateBulkDocumentsBar();
});
$('#applyBulkDocs').addEventListener('click',async()=>{
  if(!selectedDocumentIds.size)return;
  const fields={};
  const caseMode=$('#bulkCaseMode').value;
  if(caseMode==='set'){
    const name=$('#bulkCaseName').value.trim();
    if(!name){showAppNotice('Enter a case name or choose Clear case.');return}
    fields.case_name=name;
  }else if(caseMode==='clear'){
    fields.case_name=null;
  }

  const profile=$('#bulkProfile').value;
  if(profile)fields.profile=profile;

  const action=$('#bulkAction').value;
  if(action!=='__keep__')fields.action_required=action||null;

  if(!Object.keys(fields).length){showAppNotice('Choose at least one bulk change.');return}

  try{
    const result=await api('/api/documents/batch-update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:[...selectedDocumentIds],fields})});
    showAppNotice(`${result.updated} documents updated.`,'ok');
    selectedDocumentIds.clear();
    $('#bulkCaseMode').value='';
    $('#bulkCaseName').value='';
    $('#bulkProfile').value='';
    $('#bulkAction').value='__keep__';
    await loadDocuments();
    await loadCases();
  }catch(e){showAppNotice(e.message)}
});
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
async function loadCases(){
  const cs=await api('/api/cases');
  $('#caseList').innerHTML=cs.length?cs.map((c,index)=>`<div class="listItem caseCard">
    <div class="listItemHead"><div><h3>${esc(c.name)}</h3><div class="meta"><span>${c.document_count} documents</span><span>${c.open_actions} open actions</span><span>${esc((c.profiles||[]).join(', '))}</span>${c.next_deadline?`<span>next deadline ${fmtDate(c.next_deadline)}</span>`:''}${c.overdue_deadlines?`<span class="dangerText">${c.overdue_deadlines} overdue</span>`:''}</div></div><span class="badge">${c.document_count}</span></div>
    <div class="caseTimeline">${c.timeline.map(t=>`<div class="caseTimelineRow"><div><strong>${fmtDate((t.date||'').slice(0,10))}</strong><div>${esc(t.name)}</div><div class="meta"><span>${esc(t.document_type||'document')}</span><span>${esc(t.category||'')}</span><span>${esc(t.profile||'Home')}</span>${t.action?`<span>${esc(t.action)}</span>`:''}${t.deadline?`<span>deadline ${fmtDate(t.deadline)}</span>`:''}</div></div><button class="secondary caseOpen" data-path="${esc(t.path)}">Open</button></div>`).join('')}</div>
    <div class="lifePilotActions"><button class="secondary caseSummaryPreview" data-case="${esc(c.name)}" data-target="caseSummary-${index}">Podgląd podsumowania</button><a class="buttonLink secondary" href="/api/lifepilot/case-summary/export?case_name=${encodeURIComponent(c.name)}">Pobierz podsumowanie .md</a></div>
    <div class="proofPackPreview hidden" id="caseSummary-${index}"></div>
  </div>`).join(''):'<p class="muted">Assign documents to cases to build timelines.</p>';
  $$('.caseOpen').forEach(button=>button.addEventListener('click',()=>reveal(button.dataset.path)));
  $$('.caseSummaryPreview').forEach(button=>button.addEventListener('click',async()=>{
    const box=$(`#${button.dataset.target}`);
    if(!box)return;
    if(!box.classList.contains('hidden')){box.classList.add('hidden');return}
    box.classList.remove('hidden');
    box.innerHTML='<p class="muted">Tworzę lokalny podgląd sprawy…</p>';
    try{
      const summary=await api(`/api/lifepilot/case-summary?case_name=${encodeURIComponent(button.dataset.case||'')}`);
      box.innerHTML=`<div class="proofPreviewHead"><strong>LifePilot — podsumowanie sprawy</strong><span class="badge">${summary.document_count} dokumentów</span></div><div class="meta"><span>Otwarte działania: ${summary.open_actions}</span><span>Najbliższy termin: ${summary.next_deadline?fmtDate(summary.next_deadline):'brak'}</span><span>Wysyłka do chmury: nie</span></div><div class="caseSummaryPreview">${(summary.timeline||[]).map(item=>`<div class="caseSummaryRow"><strong>${esc(item.document_date||'brak daty')} — ${esc(item.name||'Dokument')}</strong><div class="meta"><span>${esc(item.document_type||'document')}</span>${item.issuer?`<span>${esc(item.issuer)}</span>`:''}${item.deadline?`<span>termin ${fmtDate(item.deadline)}</span>`:''}${item.action_required?`<span>${esc(item.action_required)}</span>`:''}</div></div>`).join('')}</div><p class="muted">Podgląd nie zawiera pełnego OCR ani lokalnych ścieżek plików.</p>`;
    }catch(e){box.innerHTML=`<p class="dangerText">${esc(e.message)}</p>`}
  }));
}

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

$('#diffBtn').addEventListener('click',async()=>{try{const r=await api('/api/diff/select',{method:'POST'});if(r.cancelled)return;$('#diffOutput').textContent=`Similarity: ${(r.similarity*100).toFixed(1)}%\nAdded lines: ${r.added_lines}\nRemoved lines: ${r.removed_lines}\n\n${r.diff}`;}catch(e){showAppNotice(e.message)}});
$('#scanCleanBtn')?.addEventListener('click',async()=>{try{$('#scanCleanOutput').innerHTML='<p class="muted">Cleaning scan…</p>';const r=await api('/api/scan/clean-select',{method:'POST'});if(r.cancelled){$('#scanCleanOutput').innerHTML='';return}$('#scanCleanOutput').innerHTML=`<p><strong>Clean copy created</strong></p><p class="muted">Quality ${r.quality.score}/100 · ${esc((r.notes||[]).join(' · '))}</p><button class="secondary" id="openCleanScan">Show in Explorer</button>`;$('#openCleanScan').addEventListener('click',()=>reveal(r.path));}catch(e){showAppNotice(e.message)}});
$('#batchBtn').addEventListener('click',async()=>{try{$('#batchOutput').innerHTML='<p class="muted">Indexing…</p>';const r=await api('/api/batch/select-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:100})});if(r.cancelled){$('#batchOutput').innerHTML='';return}$('#batchOutput').innerHTML=`<p><strong>${r.indexed}</strong> documents indexed from ${esc(r.folder)}</p>${r.errors.length?`<p class="dangerText">${r.errors.length} errors</p>`:''}`;}catch(e){showAppNotice(e.message)}});
$('#emailImportBtn').addEventListener('click',async()=>{try{$('#emailOutput').innerHTML='<p class="muted">Importing…</p>';const r=await api('/api/email/import-eml',{method:'POST'});if(r.cancelled){$('#emailOutput').innerHTML='';return}$('#emailOutput').innerHTML=`<p><strong>${r.attachments.length}</strong> attachments imported from ${esc(r.subject||'email')}</p>`;}catch(e){showAppNotice(e.message)}});

$('#watchBtn').addEventListener('click',async()=>{try{const r=await api('/api/watch/select-folder',{method:'POST'});if(!r.cancelled)loadWatch()}catch(e){showAppNotice(e.message)}});async function loadWatch(){const r=await api('/api/watch');$('#watchStatus').textContent=r.watch_folder?`Watching: ${r.watch_folder} · ${r.active?'active':'starting'}`:'No watched folder configured.'}
function resetRuleEditor(){
  editingRuleId=null;
  ['#ruleName','#ruleIssuer','#ruleText','#ruleDocType','#ruleCategory','#ruleProfile','#ruleTags'].forEach(selector=>{$(selector).value=''});
  $('#addRuleBtn').textContent='Add rule';
  $('#cancelRuleEditBtn').classList.add('hidden');
}

async function loadRules(){
  const rules=await api('/api/rules');
  const display=[...rules].reverse();
  $('#rulesList').innerHTML=display.length?display.map(x=>{
    const state=x.enabled?'ENABLED':'PAUSED';
    const conditions=Object.entries(x.condition||{}).filter(([,v])=>v).map(([k,v])=>`${k}: ${v}`).join(' · ')||'all documents';
    const targets=[x.target_category?`category: ${x.target_category}`:'',x.target_profile?`profile: ${x.target_profile}`:'',(x.target_tags||[]).length?`tags: ${x.target_tags.join(', ')}`:''].filter(Boolean).join(' · ')||'no output changes';
    const encoded=encodeURIComponent(JSON.stringify(x));
    return `<div class="listItem"><div class="listItemHead"><div><strong>${esc(x.name)}</strong> <span class="badge ${x.enabled?'':'warn'}">${state}</span></div><div class="inline"><button class="secondary ruleEdit" data-rule="${encoded}">Edit</button><button class="secondary ruleToggle" data-id="${x.id}" data-enabled="${x.enabled?'1':'0'}">${x.enabled?'Pause':'Enable'}</button><button class="secondary ruleDelete" data-id="${x.id}" data-name="${esc(x.name)}">Delete</button></div></div><div class="meta"><span>${esc(conditions)}</span><span>→ ${esc(targets)}</span></div></div>`;
  }).join(''):'<p class="muted">No rules yet.</p>';

  $$('.ruleEdit').forEach(btn=>btn.addEventListener('click',()=>{
    const rule=JSON.parse(decodeURIComponent(btn.dataset.rule));
    editingRuleId=rule.id;
    $('#ruleName').value=rule.name||'';
    $('#ruleIssuer').value=rule.condition?.issuer_contains||'';
    $('#ruleText').value=rule.condition?.text_contains||'';
    $('#ruleDocType').value=rule.condition?.document_type||'';
    $('#ruleCategory').value=rule.target_category||'';
    $('#ruleProfile').value=rule.target_profile||'';
    $('#ruleTags').value=(rule.target_tags||[]).join(', ');
    $('#addRuleBtn').textContent='Save changes';
    $('#cancelRuleEditBtn').classList.remove('hidden');
    $('#ruleName').focus();
  }));

  $$('.ruleToggle').forEach(btn=>btn.addEventListener('click',async()=>{
    const enabled=btn.dataset.enabled!=='1';
    try{
      await api(`/api/rules/${btn.dataset.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})});
      showAppNotice(enabled?'Rule enabled.':'Rule paused.','ok');
      await loadRules();
    }catch(e){showAppNotice(e.message)}
  }));

  $$('.ruleDelete').forEach(btn=>btn.addEventListener('click',async()=>{
    if(!confirm(`Delete rule "${btn.dataset.name}"? This does not change documents already processed.`))return;
    try{
      await api(`/api/rules/${btn.dataset.id}`,{method:'DELETE'});
      if(String(editingRuleId)===btn.dataset.id)resetRuleEditor();
      showAppNotice('Rule deleted.','ok');
      await loadRules();
    }catch(e){showAppNotice(e.message)}
  }));
}

$('#cancelRuleEditBtn').addEventListener('click',resetRuleEditor);

$('#addRuleBtn').addEventListener('click',async()=>{
  const p={
    name:$('#ruleName').value.trim()||'Rule',
    condition:{issuer_contains:$('#ruleIssuer').value.trim()||undefined,text_contains:$('#ruleText').value.trim()||undefined,document_type:$('#ruleDocType').value.trim()||undefined},
    target_category:$('#ruleCategory').value.trim()||null,
    target_profile:$('#ruleProfile').value.trim()||null,
    target_tags:$('#ruleTags').value.split(',').map(x=>x.trim()).filter(Boolean)
  };
  try{
    if(editingRuleId){
      await api(`/api/rules/${editingRuleId}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
      showAppNotice('Rule updated.','ok');
    }else{
      await api('/api/rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
      showAppNotice('Rule added. Newer matching rules take precedence.','ok');
    }
    resetRuleEditor();
    await loadRules();
  }catch(e){showAppNotice(e.message)}
});
async function loadTypes(){const r=await api('/api/custom-types');$('#typesList').innerHTML=r.length?r.map(x=>`<div class="listItem"><strong>${esc(x.name)}</strong><div class="meta"><span>${esc(x.keywords.join(', '))}</span><span>→ ${esc(x.category)}</span></div></div>`).join(''):'<p class="muted">No custom types.</p>'}
$('#addTypeBtn').addEventListener('click',async()=>{const p={name:$('#typeName').value.trim(),keywords:$('#typeKeywords').value.split(',').map(x=>x.trim()).filter(Boolean),category:$('#typeCategory').value||'Documents'};try{await api('/api/custom-types',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});loadTypes()}catch(e){showAppNotice(e.message)}});
$('#auditBtn').addEventListener('click',async()=>{const r=await api('/api/audit?limit=100');$('#auditList').innerHTML=r.map(x=>`<div class="listItem"><strong>${esc(x.event)}</strong><div class="meta"><span>${esc(x.created_at)}</span><span>${esc(JSON.stringify(x.payload))}</span></div></div>`).join('')});

let diagnosticsCache=null;
async function loadDiagnostics(){
  const out=$('#diagnosticsStatus');
  if(!out)return;
  out.textContent='Loading diagnostics…';
  try{
    const d=await api('/api/diagnostics');
    diagnosticsCache=d;
    out.innerHTML=`<div class="diagGrid"><span><b>Version</b> ${esc(d.version)}</span><span><b>Mode</b> ${d.packaged?'installed/portable':'source'}</span><span><b>Documents</b> ${d.documents}</span><span><b>Database</b> ${esc(d.database)} · integrity ${esc(d.database_integrity||'unknown')}</span><span><b>Schema</b> v${d.schema_version} / supported v${d.supported_schema_version}</span><span><b>Recovery readiness</b> ${esc(d.recovery_status||'unknown')}</span><span><b>Verified recovery points</b> ${d.verified_recovery_points??0}</span><span><b>Latest recovery point</b> ${d.latest_recovery_point?esc(d.latest_recovery_point):'none'}</span><span><b>Migration backups</b> ${d.migration_backups}</span><span><b>Upgrade recovery</b> ${esc(d.upgrade_recovery?.status||'not-run')}</span><span><b>Config format</b> v${d.portable_config_format}</span><span><b>Free space</b> ${d.free_space_gb} GB</span><span><b>Data folder</b> ${esc(d.data_root)}</span></div><div class="reviewReason"><strong>Recovery</strong><p>${esc(d.recovery_message||'Recovery status unavailable.')}</p></div>`;
    const advice=$('#diagnosticsAdvice');
    const assessment=d.assessment||{status:'ok',checks:[],recommendations:[]};
    const badgeClass=assessment.status==='error'?'red':assessment.status==='warning'?'warn':'';
    const label=assessment.status==='error'?'ACTION REQUIRED':assessment.status==='warning'?'CHECK RECOMMENDED':'HEALTHY';
    advice.innerHTML=`<div class="listItem"><div class="listItemHead"><strong>Diagnostic status</strong><span class="badge ${badgeClass}">${label}</span></div>${(assessment.checks||[]).map(item=>`<div class="meta"><span>${esc(item.code)}</span><span>${esc(item.message)}</span></div>`).join('')}${(assessment.recommendations||[]).length?`<div class="reviewReason"><strong>Next steps</strong><ul>${assessment.recommendations.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></div>`:''}</div>`;
  }catch(e){out.textContent=e.message;const advice=$('#diagnosticsAdvice');if(advice)advice.innerHTML=''}
}
$('#diagRefreshBtn')?.addEventListener('click',loadDiagnostics);
$('#openDataBtn')?.addEventListener('click',async()=>{try{const d=diagnosticsCache||await api('/api/diagnostics');await reveal(d.data_root)}catch(e){showAppNotice(e.message)}});
$('#openLogBtn')?.addEventListener('click',async()=>{try{const d=diagnosticsCache||await api('/api/diagnostics');await reveal(d.log_path)}catch(e){showAppNotice(e.message)}});
$('#copyDiagBtn')?.addEventListener('click',async()=>{try{const d=diagnosticsCache||await api('/api/diagnostics');await navigator.clipboard.writeText(JSON.stringify(d.safe_report,null,2));showAppNotice('Safe diagnostic report copied. It does not include document contents or local paths.','ok')}catch(e){showAppNotice(e.message)}});

async function loadRecoveryPoints(){
  const target=$('#recoveryList');
  if(!target)return;
  target.textContent='Loading recovery points…';
  try{
    const points=await api('/api/recovery');
    target.innerHTML=points.length?points.map(point=>{
      const label=point.kind==='checkpoint'?'Recovery checkpoint':point.kind==='migration'?'Migration backup':point.kind==='pre-restore'?'Pre-restore backup':'Pre-restore raw copy';
      const canRestore=point.integrity==='ok'&&Number(point.schema_version||0)<=Number(diagnosticsCache?.supported_schema_version||999);
      return `<div class="listItem"><div class="listItemHead"><strong>${esc(label)}</strong><div class="inline"><span class="badge ${point.integrity==='ok'?'':'red'}">${esc(point.integrity)}</span>${canRestore?`<button class="secondary recoveryRestore" data-name="${esc(point.name)}">Restore</button>`:''}</div></div><div class="meta"><span>${esc(point.name)}</span><span>schema v${point.schema_version??'?'}</span><span>${Math.max(1,Math.round((point.size_bytes||0)/1024))} KB</span><span>${esc(point.modified_at)}</span></div></div>`;
    }).join(''):'<p class="muted">No recovery points yet.</p>';
    $$('.recoveryRestore').forEach(button=>button.addEventListener('click',async()=>{
      const typed=prompt(`Restore database from "${button.dataset.name}"? Type RESTORE to continue.`);
      if(typed!=='RESTORE')return;
      button.disabled=true;
      try{
        const result=await api('/api/recovery/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:button.dataset.name,confirm:'RESTORE'})});
        diagnosticsCache=null;
        showAppNotice(`Database restored from ${result.restored_from.name}. A pre-restore safety copy was kept.`,'ok');
        await loadDiagnostics();
        await loadRecoveryPoints();
        await loadDashboard();
      }catch(e){showAppNotice(e.message)}
      finally{button.disabled=false}
    }));
  }catch(e){target.textContent=e.message}
}
$('#recoveryRefreshBtn')?.addEventListener('click',()=>runLoad(loadRecoveryPoints));
$('#recoveryCheckpointBtn')?.addEventListener('click',async()=>{
  const button=$('#recoveryCheckpointBtn');
  button.disabled=true;
  try{
    const point=await api('/api/recovery/checkpoint',{method:'POST'});
    showAppNotice(`Recovery checkpoint created: ${point.name}`,'ok');
    await loadRecoveryPoints();
    await loadDiagnostics();
  }catch(e){showAppNotice(e.message)}
  finally{button.disabled=false}
});


async function loadNotificationStatus(){
  try{const r=await api('/api/notifications/status');$('#notifyStatus').textContent=r.enabled?`LifePilot notifications enabled · ${r.pending||0} item(s) within ${r.days_ahead} day(s)`:`LifePilot notifications disabled · ${r.pending||0} item(s) currently match the selected horizon.`;$('#notifyDays').value=r.days_ahead||3;}catch(e){$('#notifyStatus').textContent=e.message}
}
$('#notifyEnableBtn')?.addEventListener('click',async()=>{try{const days=Number($('#notifyDays').value||3);const r=await api('/api/notifications/enable',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({days_ahead:days})});await loadNotificationStatus();showAppNotice(`LifePilot notifications enabled. Test notifications shown: ${r.test_notifications}.`,'ok');}catch(e){showAppNotice(e.message)}});
$('#notifyDisableBtn')?.addEventListener('click',async()=>{try{await api('/api/notifications/disable',{method:'POST'});loadNotificationStatus()}catch(e){showAppNotice(e.message)}});

async function readPortableConfigFile(){
  const file=$('#configImportFile')?.files?.[0];
  if(!file)throw new Error('Choose a DocPilot configuration JSON first.');
  let payload;
  try{payload=JSON.parse(await file.text())}catch{throw new Error('The selected file is not valid JSON.')}
  return payload;
}

async function previewPortableConfig(){
  const out=$('#configImportPreview'), apply=$('#configApplyBtn');
  apply.disabled=true;
  pendingPortableConfig=null;
  out.textContent='Checking configuration…';
  try{
    const payload=await readPortableConfigFile();
    const preview=await api('/api/config/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    pendingPortableConfig=payload;
    apply.disabled=false;
    const reconnect=(preview.reconnect_required||[]).map(item=>'<li>'+esc(item)+'</li>').join('');
    out.innerHTML='<p><strong>Rules:</strong> '+preview.rules.add+' add · '+preview.rules.update+' update</p><p><strong>Custom types:</strong> '+preview.custom_types.add+' add · '+preview.custom_types.update+' update</p>'+(reconnect?'<p><strong>Reconnect / re-enable after import:</strong></p><ul>'+reconnect+'</ul>':'<p>No connector re-authentication requested by this file.</p>');
  }catch(e){out.textContent=e.message}
}

$('#configImportFile')?.addEventListener('change',()=>{pendingPortableConfig=null;$('#configApplyBtn').disabled=true;$('#configImportPreview').textContent='File selected. Preview it before importing.'});
$('#configPreviewBtn')?.addEventListener('click',previewPortableConfig);
$('#configApplyBtn')?.addEventListener('click',async()=>{
  if(!pendingPortableConfig)return;
  if(!confirm('Apply this portable configuration? Existing rules and custom types with the same names will be updated. Credentials and machine-specific paths will not be imported.'))return;
  const btn=$('#configApplyBtn');
  btn.disabled=true;
  try{
    const result=await api('/api/config/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pendingPortableConfig)});
    showAppNotice('Configuration imported: '+result.rules_added+' rules added, '+result.rules_updated+' updated, '+result.custom_types_added+' custom types added, '+result.custom_types_updated+' updated.','ok');
    pendingPortableConfig=null;
    $('#configImportFile').value='';
    $('#configImportPreview').textContent=(result.reconnect_required||[]).length?'Import complete. Reconnect: '+result.reconnect_required.join(' · '):'Import complete. No connector reconnection required.';
    await loadRules();
    await loadTypes();
    await loadIntegrationStatus();
    await loadNotificationStatus();
  }catch(e){showAppNotice(e.message);btn.disabled=false}
});
function integrationScope(){
  return {
    profile:$('#integrationScopeProfile')?.value||'',
    case_name:$('#integrationScopeCase')?.value.trim()||'',
    action_required:$('#integrationScopeAction')?.value||'',
    category:$('#integrationScopeCategory')?.value.trim()||'',
    limit:Math.max(1,Math.min(Number($('#integrationScopeLimit')?.value||100),500))
  };
}

async function loadIntegrationHistory(){
  const target=$('#integrationHistory');
  if(!target)return;
  try{
    const runs=await api('/api/integrations/history?limit=20');
    if(!runs.length){target.innerHTML='<p class="muted">No integration runs yet.</p>';return}
    target.innerHTML=runs.map(run=>{
      const scope=run.scope||{};
      const parts=[];
      if(scope.profile)parts.push('profile: '+scope.profile);
      if(scope.case_name)parts.push('case: '+scope.case_name);
      if(scope.action_required)parts.push('action: '+scope.action_required);
      if(scope.category)parts.push('category: '+scope.category);
      if(scope.calendar_id)parts.push('calendar: '+scope.calendar_id);
      if(scope.unread_only!==undefined)parts.push(scope.unread_only?'unread only':'all messages');
      const errors=(run.errors||[]).slice(0,2);
      const badge=run.status==='success'?'':(run.status==='partial'?'warn':'red');
      return '<div class="listItem"><div class="listItemHead"><strong>'+esc(run.provider)+' · '+esc(run.operation)+'</strong><span class="badge '+badge+'">'+esc(run.status)+'</span></div><div class="meta"><span>'+esc(run.started_at||'')+'</span><span>'+run.attempted+' attempted</span><span>'+run.succeeded+' succeeded</span><span>'+run.skipped+' skipped</span><span>'+run.failed+' failed</span></div><div class="muted">'+esc(parts.join(' · ')||'all eligible records')+'</div>'+(errors.length?'<div class="reviewReason">'+esc(errors.join(' · '))+'</div>':'')+'</div>';
    }).join('');
  }catch(e){target.innerHTML='<p class="muted">'+esc(e.message)+'</p>'}
}
async function loadIntegrationStatus(){
  try{
    const [r,catalog]=await Promise.all([api('/api/integrations/status'),api('/api/integrations/catalog')]);
    $('#emailConnectorStatus').textContent=r.email.configured?`${r.email.provider}: ${r.email.email} · ${r.email.secret_available?'credential stored':'credential missing'}`:'Not configured.';
    $('#notionStatus').textContent=r.notion.configured?`Configured · database ${r.notion.database_id}`:'Not configured.';
    $('#googleStatus').textContent=r.google_calendar.configured?`OAuth client selected · ${r.google_calendar.authorized?'authorized':'authorization will open on first sync'}`:'Not configured.';
    const select=$('#integrationPreviewProvider');
    if(select){
      const current=select.value;
      const options=(catalog||[]).filter(item=>item.supports_scope&&item.supports_document_sync);
      select.innerHTML=options.map(item=>`<option value="${esc(item.key)}">${esc(item.label)}</option>`).join('');
      if(options.some(item=>item.key===current))select.value=current;
    }
  }catch(e){console.warn(e)}
}
$('#integrationPreviewBtn')?.addEventListener('click',async()=>{
  const out=$('#integrationPreviewOutput');
  out.textContent='Checking scope…';
  try{
    const r=await api('/api/integrations/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:$('#integrationPreviewProvider').value,scope:integrationScope()})});
    const names=(r.sample||[]).map(item=>item.name).join(' · ');
    out.innerHTML='<strong>'+r.eligible+'</strong> eligible from '+r.matched_total+' matching records (limit '+r.scope.limit+').'+(names?'<br><span class="muted">Sample: '+esc(names)+'</span>':'');
  }catch(e){out.textContent=e.message}
});
$('#integrationHistoryRefreshBtn')?.addEventListener('click',()=>runLoad(loadIntegrationHistory));
$('#emailConfigureBtn')?.addEventListener('click',async()=>{try{await api('/api/integrations/email',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:$('#emailProvider').value,email:$('#emailAddress').value,password:$('#emailPassword').value,folder:$('#emailFolder').value||'INBOX'})});$('#emailPassword').value='';loadIntegrationStatus()}catch(e){showAppNotice(e.message)}});
$('#emailImapImportBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/email/import-imap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({unread_only:true,max_messages:20})});showAppNotice('Imported '+r.attachments.length+' attachment(s).'+(r.errors?.length?' '+r.errors.length+' error(s).':''),r.errors?.length?'error':'ok');await loadDashboard();await loadIntegrationHistory()}catch(e){showAppNotice(e.message);loadIntegrationHistory()}});
$('#notionConfigureBtn')?.addEventListener('click',async()=>{try{await api('/api/integrations/notion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:$('#notionToken').value,database_id:$('#notionDatabase').value})});$('#notionToken').value='';loadIntegrationStatus()}catch(e){showAppNotice(e.message)}});
$('#notionSyncBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/integrations/notion/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:integrationScope()})});showAppNotice('Notion sync: '+r.synced+' changed, '+(r.skipped||0)+' unchanged of '+r.attempted+' attempted.'+(r.errors?.length?' '+r.errors.length+' error(s).':''),r.errors?.length?'error':'ok');await loadIntegrationHistory()}catch(e){showAppNotice(e.message);loadIntegrationHistory()}});
$('#googleClientBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/integrations/google-calendar/select-client',{method:'POST'});if(!r.cancelled)loadIntegrationStatus()}catch(e){showAppNotice(e.message)}});
$('#googleSyncBtn')?.addEventListener('click',async()=>{try{const r=await api('/api/integrations/google-calendar/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({calendar_id:'primary',scope:integrationScope()})});showAppNotice('Google Calendar sync: '+r.synced+' changed, '+(r.skipped||0)+' unchanged of '+r.attempted+' eligible deadline(s).'+(r.errors?.length?' '+r.errors.length+' error(s).':''),r.errors?.length?'error':'ok');await loadIntegrationHistory();loadIntegrationStatus()}catch(e){showAppNotice(e.message);loadIntegrationHistory()}});

$('#changesBtn').addEventListener('click',async()=>{
  const r=await api('/api/changes');
  $('#changesList').innerHTML=r.length?r.map(x=>`<div class="listItem"><strong>${esc(x.action)}: ${esc(x.destination)}</strong><div class="meta"><span>${esc(x.created_at)}</span></div><button class="secondary historyUndo" data-id="${x.id}">Undo</button></div>`).join(''):'<p class="muted">No reversible changes.</p>';
  $$('.historyUndo').forEach(b=>b.addEventListener('click',async()=>{try{const u=await api(`/api/undo/${b.dataset.id}`,{method:'POST'});showAppNotice(`Restored to: ${u.restored_to}`,'ok');$('#changesBtn').click()}catch(e){showAppNotice(e.message)}}));
});

loadSetupStatus().finally(()=>runLoad(loadDashboard));
