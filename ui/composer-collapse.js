const STORAGE_KEY='h3.composer.collapsed';

export function initComposerCollapse({getSummary}){
 const composer=document.querySelector('#composer'),area=composer.closest('.composer-area'),prompt=document.querySelector('#prompt');
 const bar=document.createElement('div');bar.className='prompt-bar';
 const toggle=document.createElement('button');toggle.type='button';toggle.id='prompt-collapse';toggle.className='prompt-collapse';toggle.setAttribute('aria-controls','composer');
 const label=document.createElement('span'),chevron=document.createElement('span');chevron.className='prompt-collapse-chevron';chevron.setAttribute('aria-hidden','true');toggle.append(chevron,label);
 const summary=document.createElement('span');summary.className='prompt-collapsed-summary';
 bar.append(toggle,summary,document.querySelector('#stop'));composer.before(bar);
 const body=document.createElement('div');body.className='prompt-body';body.id='prompt-body';
 for(const child of [...composer.children])if(!child.classList.contains('composer-bottom'))body.append(child);
 composer.prepend(body);
 let collapsed=false;
 try{collapsed=localStorage.getItem(STORAGE_KEY)==='true';}catch{}
 function render(){
  area.classList.toggle('prompt-is-collapsed',collapsed);composer.hidden=collapsed;
  toggle.setAttribute('aria-expanded',String(!collapsed));label.textContent=collapsed?'Mostra prompt':'Nascondi prompt';
  chevron.textContent=collapsed?'⌄':'⌃';
  summary.textContent=getSummary();summary.title=summary.textContent;
 }
 function set(value,{remember=false,focus=false}={}){
  collapsed=value;
  if(remember)try{localStorage.setItem(STORAGE_KEY,String(value));}catch{}
  render();
  if(focus&&!value){body.scrollTop=0;prompt.focus({preventScroll:true});}
 }
 toggle.onclick=()=>set(!collapsed,{remember:true,focus:collapsed});
 composer.addEventListener('input',render);composer.addEventListener('change',render);
 render();
 return {render,reveal:()=>set(false,{focus:true})};
}
