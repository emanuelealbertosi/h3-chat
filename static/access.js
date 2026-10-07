const $=s=>document.querySelector(s);let access,users=[];
const error=text=>{const box=$('#access-error');box.textContent=text;box.hidden=!text;};
async function api(path,body,method='POST'){
 const response=await fetch('/api/auth/'+path,{cache:'no-store',method:body===undefined?'GET':method,headers:body===undefined?{}:{'Content-Type':'application/json','X-H3-Token':access?.csrf||''},body:body===undefined?undefined:JSON.stringify(body)});
 const value=await response.json();if(!response.ok)throw Error(value.error||'Operazione non riuscita.');return value;
}
function form(id,fn){const element=$(id);if(element)element.onsubmit=async e=>{e.preventDefault();error('');const button=element.querySelector('button');button.disabled=true;try{await fn(Object.fromEntries(new FormData(element)),element);}catch(e){error(e.message);}finally{button.disabled=false;}};}
function button(text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=async()=>{error('');b.disabled=true;try{await fn();}catch(e){error(e.message);}finally{b.disabled=false;}};return b;}
function row(title,note){const element=document.createElement('div');element.className='item';const label=document.createElement('div'),name=document.createElement('strong'),small=document.createElement('small');name.textContent=title;small.textContent=note;label.append(name,small);const actions=document.createElement('div');actions.className='actions';element.append(label,actions);return {element,actions};}
async function refresh(){
 access=await api('me');
 if(!access.user){location.replace('/login');return;}
 if(!access.configured){$('#owner-setup').hidden=false;return;}
 $('#keys-section').hidden=false;$('#password-section').hidden=false;$('#logout').hidden=false;
 if(access.user.role==='owner'){
  $('#users-section').hidden=false;$('#key-user-label').hidden=false;users=(await api('users')).users;$('#user-list').replaceChildren();$('#key-user').replaceChildren();
  for(const user of users){
   if(user.enabled){const option=document.createElement('option');option.value=user.id;option.textContent=user.name;$('#key-user').append(option);}
   const item=row(user.name,user.role==='owner'?'Amministratore · spazio originale':user.enabled?'Ospite · spazio separato':'Ospite · accesso revocato');
   if(user.role==='guest'){
    item.actions.append(button(user.enabled?'Revoca accesso':'Riattiva',async()=>{await api('users/'+user.id,{enabled:!user.enabled},'PATCH');await refresh();}));
    item.actions.append(button('Nuova password',async()=>{
     const reset=document.createElement('form'),input=document.createElement('input'),submit=document.createElement('button');
     input.type='password';input.autocomplete='new-password';input.placeholder='Nuova password · almeno 12 caratteri';input.minLength=12;input.maxLength=256;input.required=true;input.setAttribute('aria-label','Nuova password per '+user.name);submit.textContent='Salva password';reset.append(input,submit);item.element.append(reset);input.focus();
     reset.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{await api('users/'+user.id,{password:input.value},'PATCH');await refresh();}catch(e){error(e.message);submit.disabled=false;}};
    }));
   }
   $('#user-list').append(item.element);
  }
 }
 const keys=(await api('keys')).keys;$('#key-list').replaceChildren();
 for(const key of keys){const item=row(key.name,key.username+' · scade '+new Date(key.expires*1000).toLocaleDateString());item.actions.append(button('Revoca',async()=>{await api('keys/'+key.id,{},'DELETE');await refresh();}));$('#key-list').append(item.element);}
}
function confirmPassword(body){if(body.password!==body.confirm)throw Error('Le password non coincidono.');delete body.confirm;}
form('#login-form',async body=>{await api('login',body);location.assign('/');});
form('#key-form',async body=>{await api('login',body);location.assign('/');});
form('#setup-form',async body=>{confirmPassword(body);await api('setup',body);location.assign('/access');});
form('#guest-form',async(body,element)=>{await api('users',body);element.reset();await refresh();});
form('#create-key-form',async body=>{if(access.user.role!=='owner')delete body.user_id;body.days=Number(body.days);const result=await api('keys',body);$('#key-value').value=result.key;$('#new-key').hidden=false;await refresh();});
form('#password-form',async body=>{confirmPassword(body);await api('password',body);location.assign('/login');});
if($('#logout'))$('#logout').onclick=async()=>{try{await api('logout',{});location.assign('/login');}catch(e){error(e.message);}};
if($('#copy-key'))$('#copy-key').onclick=async()=>{try{await navigator.clipboard.writeText($('#key-value').value);$('#copy-key').textContent='Copiata';}catch{error('Seleziona la chiave e copiala manualmente.');}};
try{
 access=await api('me');
 if($('#login-form')){
  if(access.configured&&access.user){location.replace('/');}
  if(!access.configured){$('#setup-notice').hidden=false;$('#login-form').hidden=true;$('#key-login').hidden=true;if(access.local)location.replace('/access');}
 }else await refresh();
}catch(e){error(e.message);}
