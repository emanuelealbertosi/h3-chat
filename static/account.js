// Kept independent of the chat bundle so login also works on portable builds.
const startupButtons=['#new-chat','#new-project'].map(s=>document.querySelector(s)).filter(Boolean);
startupButtons.forEach(b=>b.disabled=true);
const ready=()=>{if(!document.querySelector('#generation-settings')?.textContent.includes(' · Contesto '))return;startupButtons.forEach(b=>b.disabled=false);loading.disconnect();};
const loading=new MutationObserver(ready);loading.observe(document.body,{childList:true,subtree:true,characterData:true});ready();
const response=await fetch('/api/auth/me',{cache:'no-store'});
if(response.ok){
 const access=await response.json();
 if(access.user){
  const link=document.createElement('a');link.href='/access';link.className='btn small';link.id='account-access';link.textContent=access.user.role==='owner'?'Accessi':access.user.name;link.title='Account, password e chiavi di accesso';document.querySelector('.top-actions').prepend(link);
  if(access.user.role==='guest'){
   document.body.classList.add('guest-account');
   const style=document.createElement('style');style.textContent='.guest-account #settings-open,.guest-account #setup-nudge,.guest-account #memory-status,.guest-account #generation-settings,.guest-account #project-paths,.guest-account #project-folder,.guest-account #project-add{display:none!important}.guest-account #project-paths + .project-actions{margin-top:0}';document.head.append(style);
   // Hide the server-filesystem picker; browser upload and drag/drop remain.
   const hidePaths=()=>{document.querySelector('#project-paths')?.closest('label')?.setAttribute('hidden','');};
   new MutationObserver(hidePaths).observe(document.body,{childList:true,subtree:true});hidePaths();
  }
 }
}
const originalFetch=window.fetch.bind(window);
window.fetch=async (...args)=>{const response=await originalFetch(...args);if(response.status===401&&!String(args[0]).includes('/api/auth/'))location.assign('/login');return response;};
