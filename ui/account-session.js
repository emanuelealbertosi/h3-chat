export async function logoutAccount({request=fetch,navigate=url=>location.assign(url),before=async()=>{},clear=()=>{}}={}){
 await before();
 const response=await request('/api/auth/me',{cache:'no-store'}),account=await response.json();
 if(!response.ok)throw Error(account.error||'Impossibile leggere la sessione.');
 if(!account.user||!account.configured){navigate('/access');return;}
 const loggedOut=await request('/api/auth/logout',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','X-H3-Token':account.csrf},body:'{}'});
 const result=await loggedOut.json();if(!loggedOut.ok)throw Error(result.error||'Uscita non riuscita.');
 clear();navigate('/login');
}
