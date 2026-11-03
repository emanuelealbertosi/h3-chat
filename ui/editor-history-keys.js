// Reuse each editor's own history. Text fields keep native editing shortcuts.
export function editorHistoryKeys(panel,{target=panel,doc=null,undo,redo}){
 const owner=panel.ownerDocument,documents=doc?[owner,doc]:[owner];
 const handler=e=>{if(!(e.ctrlKey||e.metaKey)||e.altKey||e.target?.isContentEditable||e.target?.closest?.('input,textarea,select,[contenteditable="true"]'))return;
  if(e.currentTarget!==doc&&!panel.contains(e.target)&&!target.contains(e.target))return;
  const key=e.key.toLowerCase();if(key==='z'||key==='y'){e.preventDefault();(key==='y'||e.shiftKey?redo:undo)();}
 };
 for(const d of documents)d.addEventListener('keydown',handler);
 const observer=new MutationObserver(()=>{if(panel.isConnected)return;for(const d of documents)d.removeEventListener('keydown',handler);observer.disconnect();});observer.observe(owner.body,{childList:true,subtree:true});
}
