// Keep one scrolling surface and a reachable action footer in video tools.
export function videoDialogLayout(dialog){
 const form=dialog.querySelector('form'),body=document.createElement('div');body.className='video-dialog-body';
 for(const child of [...form.children])if(child.tagName!=='FOOTER')body.append(child);
 form.prepend(body);return body;
}
