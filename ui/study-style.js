export function studyStyles(){
 if(document.querySelector('#study-style'))return;
 const style=document.createElement('style');style.id='study-style';style.textContent=`
.study-view{max-width:100%;box-sizing:border-box;color:var(--ink,#20383b);container-type:inline-size}
.study-view *{box-sizing:border-box}.study-view [hidden]{display:none!important}
.study-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:16px}
.study-header h1{font:750 20px/1.35 Manrope,sans-serif;margin:5px 0;overflow-wrap:anywhere}
.study-eyebrow{font-size:10px;font-weight:750;letter-spacing:.07em;text-transform:uppercase;color:var(--muted,#61766b)}
.study-note{color:var(--muted,#61766b);font-size:11px;line-height:1.6;margin:6px 0}
.study-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0}
.study-toolbar select,.study-search{font:inherit;color:inherit;min-width:0;max-width:100%;padding:8px 10px;background:var(--white,#fffefa);border:1px solid var(--line,#ddd);border-radius:7px}
.study-view button{white-space:normal}.study-toolbar button[aria-pressed=true]{background:var(--green,#153d40);color:var(--white,#fffefa);border-color:var(--green,#153d40)}
.study-menu{position:relative;flex:none}.study-menu>summary,.study-index>summary,.study-audio-options>summary{cursor:pointer;font-weight:700;font-size:11px;padding:9px 0;color:var(--green,#153d40)}
.study-menu>summary{padding:7px 10px;border:1px solid var(--line,#ddd);border-radius:7px}
.study-menu-body{position:absolute;right:0;top:100%;z-index:5;min-width:210px;display:grid;gap:7px;padding:12px;background:var(--white,#fffefa);border:1px solid var(--line,#ddd);border-radius:9px;box-shadow:0 8px 24px #153d4015}
.study-menu-body button{justify-content:flex-start;text-align:left}.study-index{border-block:1px solid var(--line,#ddd);margin:12px 0 18px}
.study-index-tools{display:flex;gap:8px;margin:5px 0 10px}.study-search{width:100%}
.study-index-list{list-style:none;margin:0 0 12px;padding:0;max-height:230px;overflow:auto;scrollbar-gutter:stable}
.study-index-list button{display:flex;align-items:flex-start;gap:10px;width:100%;text-align:left;border:0;border-radius:7px;background:transparent;color:inherit;font:inherit;padding:9px 10px}
.study-index-list button:hover{background:var(--soft,#eaf0e9)}.study-index-list button[aria-current=true]{background:var(--soft,#eaf0e9);font-weight:750}
.study-index-list span{min-width:0;overflow-wrap:anywhere}.study-index-list small{flex:none;min-width:22px;color:var(--muted,#61766b)}
.study-counter{font:700 11px Manrope,sans-serif;color:var(--muted,#61766b)}
.study-meter{display:block;width:100%;height:5px;margin:10px 0 6px;accent-color:var(--green,#153d40)}
.study-card{border:1px solid var(--line,#ddd);border-radius:16px;background:var(--white,#fffefa);padding:clamp(18px,4cqw,30px);overflow-wrap:anywhere;min-width:0}
.study-card.study-flashcard{min-height:260px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center}
.study-card h2{font:750 clamp(20px,4.5cqw,28px)/1.4 Manrope,sans-serif;letter-spacing:-.03em;margin:12px 0 18px;color:inherit}
.study-answer{font-size:15px;line-height:1.8;overflow-wrap:anywhere;width:100%;overflow-x:auto}
.study-answer p{margin:0 0 10px}.study-answer p:last-child{margin-bottom:0}.study-answer :is(h1,h2,h3,h4){font:750 17px/1.5 Manrope,sans-serif;margin:12px 0}.study-answer table{border-collapse:collapse;width:100%;font-size:13px}.study-answer :is(td,th){padding:8px;border:1px solid var(--line,#ddd);text-align:left}.study-answer pre{white-space:pre-wrap;font-size:12px}.study-answer .katex-display{overflow-x:auto;overflow-y:hidden}
.study-response{width:100%;min-height:120px;padding:12px;font:14px/1.7 Manrope,sans-serif;border:1px solid var(--line,#ddd);border-radius:8px;background:var(--white,#fffefa);color:inherit;margin-bottom:12px;resize:vertical}
.study-reveal{margin-top:12px}.study-footer{display:flex;flex-direction:column;gap:10px;margin-top:14px}
.study-navigation,.study-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.study-navigation .study-counter{margin-inline:auto}
.study-actions{padding-top:12px;border-top:1px solid var(--line,#ddd)}.study-actions .study-known{background:var(--green,#153d40);color:var(--white,#fffefa)}
.study-citations{display:flex;gap:6px;flex-wrap:wrap;margin:16px 0 0}.study-citations button{font-size:10px;text-align:left;overflow-wrap:anywhere;max-width:100%}
.study-explanation{margin-top:20px;border-top:1px solid var(--line,#ddd);padding-top:14px;white-space:pre-wrap;width:100%}.study-explanation h3{font:750 15px Manrope,sans-serif}
.study-sections{display:grid;gap:16px}.study-sections .study-card{min-height:0}.study-sections h2{font-size:20px;margin-top:0}
.study-section-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.study-section-actions button{font-size:10px}
.study-faq{padding:0}.study-faq>summary{cursor:pointer;padding:18px 20px;font:700 16px/1.6 Manrope,sans-serif}.study-faq-body{padding:0 20px 20px}
.study-timeline{list-style:none;margin:0;padding:0 0 0 18px;border-left:2px solid var(--line,#ddd);display:grid;gap:20px}
.study-timeline>li{position:relative;min-width:0}.study-timeline>li:before{content:'';position:absolute;width:10px;height:10px;border:2px solid var(--white,#fffefa);background:var(--green,#153d40);border-radius:50%;left:-24px;top:24px}
.study-dialogue{display:grid;gap:14px}.study-bubble{border-radius:15px 15px 15px 3px;padding:18px 20px;background:var(--soft,#eaf0e9);max-width:94%;min-width:0;overflow-wrap:anywhere}
.study-bubble.study-speaker-b{margin-left:auto;border-radius:15px 15px 3px 15px;background:var(--white,#fffefa);border:1px solid var(--line,#ddd)}
.study-bubble h2{font:750 11px Manrope,sans-serif;margin:0 0 9px;text-transform:uppercase;letter-spacing:.05em}.study-bubble .study-answer{font-size:14px}
.study-audio-options{margin:12px 0}.study-audio-options .settings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:8px 0}.study-audio-options label{display:grid;gap:6px;font-size:11px}.study-audio-options select{max-width:100%;min-width:0}
.study-view audio{width:100%;margin:10px 0}.study-empty{padding:30px 12px;text-align:center;color:var(--muted,#61766b)}
.study-modal{width:min(850px,92vw);max-height:85vh;overflow:auto;border:1px solid var(--line,#ccc);border-radius:12px;padding:24px;color:var(--ink,#20383b);background:var(--white,#fffefa)}
.study-modal pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.8 Manrope,sans-serif}.study-modal::backdrop{background:#153d4066}
.study-source{padding:12px 0;border-top:1px solid var(--line,#ddd)}.study-source h3{font-size:14px}.study-source details{font-size:12px}
.study-edit{display:grid;gap:12px}.study-edit textarea{width:100%;min-height:120px;box-sizing:border-box;font:inherit;padding:10px;border:1px solid var(--line,#ddd);border-radius:7px}
@container(max-width:420px){.study-header{gap:8px}.study-header h1{font-size:17px}.study-card{padding:18px}.study-card.study-flashcard{min-height:220px}.study-answer{font-size:14px}.study-actions .btn{flex:1}.study-bubble{max-width:100%}.study-audio-options .settings-grid{grid-template-columns:1fr}}
@media print{.study-index,.study-toolbar,.study-menu,.study-footer,.study-section-actions,.study-audio-options{display:none!important}.study-card{break-inside:avoid}}
`;document.head.append(style);
}
