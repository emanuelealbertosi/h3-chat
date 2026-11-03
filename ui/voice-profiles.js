export const voiceProfiles=[['configured','Campione configurato'],['limpida','Limpida · italiana · Higgs BF16'],['aurora','Aurora · italiana · Higgs BF16']];
export function studyVoices(host){
 let saved={voice_a:'configured',voice_b:'configured'};try{saved={...saved,...JSON.parse(localStorage.getItem('h3-study-audio-voices')||'{}')};}catch{}
 const group=document.createElement('div');group.className='settings-grid';const fields={};
 for(const [key,name] of [['voice_a','Voce A'],['voice_b','Voce B']]){
  const label=document.createElement('label'),input=document.createElement('select');label.textContent=name;input.ariaLabel='Studio · '+name;input.dataset.studyVoice=key;
  for(const [value,text] of voiceProfiles)input.add(new Option(value==='configured'?`${text} · ${key==='voice_a'?'maschile':'femminile'}`:text,value));
  input.value=voiceProfiles.some(([v])=>v===saved[key])?saved[key]:'configured';label.append(input);group.append(label);fields[key]=input;
  input.onchange=()=>localStorage.setItem('h3-study-audio-voices',JSON.stringify(read()));
 }
 const read=()=>Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.value]));host.append(group);return{read};
}
