"""App-owned reference completeness and CPU layout checks, with bounded repair."""
import copy,json,re,unicodedata
from .downloads import Cancelled


def normalized(value):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().lower())


def measurement_regions(info):
    result=[]
    texts=[r for r in info['plan']['regions'] if r['kind']=='text' and r.get('text')]
    for image in info['plan']['regions']:
        if image['kind']!='image' or not image.get('asset_id'):continue
        x,y,w,h=image['box']
        for row in texts:
            l,t,bw,bh=row['box']
            if l>=x-.000001 and t>=y-.000001 and l+bw<=x+w+.000001 and t+bh<=y+h+.000001:
                result.append({'id':image['asset_id'],'text':row['text'],'box':[(l-x)/w,(t-y)/h,bw/w,bh/h]})
    return result


def diagnose(report,info,planned,expected_text=None,authorized_text=''):
    issues=[]
    for key in ('out_of_bounds','poster_overflow','covered_text'):
        if report.get(key):issues.append({key:report[key][:12]})
    used={m['id']:m for m in report.get('images',[]) if m.get('visible')}
    for asset in planned:
        image=used.get(asset['id'])
        if not image:issues.append({'missing_visible_image':asset['id'],'role':asset.get('role','photo')});continue
        if asset.get('role') in ('hero','photo','decoration'):
            area=image['width']*image['height']/(report['width']*report['height'])
            box=asset.get('source_box',[0,0,.2,.2])
            # A decorative illustration is not a full-width hero. Its source
            # box can include the surrounding labels and columns; requiring
            # the whole panel's area makes the repair enlarge it over the copy.
            minimum=min(.04,max(.015,box[2]*box[3]*.2)) if asset.get('role')=='decoration' else min(.1,max(.025,box[2]*box[3]*.5))
            if area<minimum:issues.append({'hero_too_small':asset['id'],'role':asset.get('role','photo'),'relative_area':round(area,4),'minimum_relative_area':round(minimum,4)})
    visible=normalized(report.get('visible_text',''))
    if any('reference_text' in m for m in report.get('images',[])):
        embedded=[normalized(t['text']) for m in used.values() for t in m.get('reference_text',[]) if t['visible']]
    else:embedded=[normalized(t) for r in info['plan']['regions'] if r.get('asset_id') in used for t in r.get('embedded_text',[])]
    def overlaps(a,b):
        area=max(0,min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x']))*max(0,min(a['y']+a['height'],b['y']+b['height'])-max(a['y'],b['y']))
        return area>=min(a['width']*a['height'],b['width']*b['height'])*.2
    if 'text_boxes' in report:
        duplicate=[]
        for image in used.values():
            for printed in image.get('reference_text',[]):
                text=normalized(printed['text'])
                if not printed['visible'] or len(text)<12:continue
                for run in report['text_boxes']:
                    typed=normalized(run['text'])
                    if len(typed)>=8 and (typed in text or text in typed) and any(overlaps(printed['box'],box) for box in run['boxes']):duplicate.append(printed['text']);break
    else:duplicate=[t for t in embedded if len(t)>=12 and t in visible]
    if duplicate:issues.append({'duplicate_raster_text':duplicate[:12],'action':'Queste scritte sono già dentro le immagini originali: non stamparle di nuovo in HTML, a meno di rimuoverle prima dalla grafica.'})
    missing=[]
    regions=info['plan']['regions'] if expected_text is None else [{'kind':'text','text':expected_text}]
    for row in regions:
        if row['kind']!='text' or row.get('facsimile') or not row.get('text','').strip():continue
        # A logo or facsimile already preserves its own internal lettering.
        if row.get('role') in ('logo','qr'):continue
        for line in row['text'].splitlines():
            text=normalized(line)
            if len(text)<4:continue
            if text not in visible and not any(text in t for t in embedded):missing.append(line[:250])
    if missing:issues.append({'missing_text':missing[:24]})
    approved=authorized_text+'\n'+'\n'.join(r.get('text','') for r in info['plan']['regions'] if (r['kind']=='text' and r.get('legibility','clear')=='clear') or (r['kind']=='image' and r.get('legibility')=='clear'))
    # A phone/email inside an unverified logo caption is not permission to
    # invent an editable footer with it. The raster itself remains preserved.
    contacts=r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\w)(?:\+\d{1,3}[ .-]?)?\d{3,5}(?:[ .-]\d{2,6}){1,4}(?!\w)'
    unverified=[value for value in re.findall(contacts,report.get('visible_text',''))
        if (sum(c.isdigit() for c in value)>=7 or '@' in value)
        and not re.fullmatch(r'(?:19|20)\d{2}\s*[-–/]\s*(?:19|20)\d{2}',value)
        and normalized(value) not in normalized(approved)]
    if unverified:issues.append({'unverified_contacts':unverified[:10],'action':'Non stampare dati di contatto non verificati. Conserva soltanto il riquadro originale, senza trascriverne i recapiti dubbi.'})
    return issues


def verify(app,deck,page,assets,info,planned,html,request,settings,cancel,stream,stage,log,folder,meta,*,user_prompt='',copy_text=''):
    from .slide_html import generate
    for attempt in range(3):
        if cancel.is_set():raise Cancelled()
        probe=copy.deepcopy(deck);probe['active']=0;probe['poster']['count']=1
        probe['pages']=[page|{'html':html,'status':'ready'}]
        stage('Locandine · controllo automatico di struttura, immagini e testi'+(' · '+str(attempt+1) if attempt else ''))
        result=app.engine.tool_call('agent-layout-worker.py',{'data':str(app.data),'deck':probe,'media':assets,'folder':str(folder/f'reference-check-{attempt+1}'),'strict_reference':True,'reference_text_regions':measurement_regions(info)},cancel,stage,log,timeout=90)
        pages=result.get('pages',[])
        if len(pages)!=1 or 'covered_text' not in pages[0] or 'visible_text' not in pages[0]:raise ValueError('Verificatore della locandina da aggiornare: mancano i controlli di visibilità.')
        # Explicit requested copy changes supersede the original lettering. An
        # ordinary "improve" must still preserve all source content.
        changed=re.search(r'\b(?:sostituisc\w*|riscriv\w*|traduc\w*|togli\w*|rimuov\w*|elimina\w*|aggiorna\w*)\b|\bcambia\w*\s+(?:il\s+|la\s+|i\s+|le\s+)?(?:titolo|test[io]|data|date|parol\w*|contatt\w*)\b',user_prompt,re.I)
        issues=diagnose(pages[0],info,planned,copy_text if changed else None,user_prompt)
        meta.setdefault('poster_reference_checks',[]).append({'attempt':attempt+1,'issues':issues,'report':result})
        if not issues:return html
        blocking=[issue for issue in issues if 'duplicate_raster_text' not in issue]
        # Repeated branding in distinct areas is legitimate, and raster text
        # rectangles do not identify individual painted glyphs. Offer one
        # correction, but never treat that heuristic alone as a failed job.
        if not blocking and attempt>=1:
            page['layout_warning']='Verifica visivamente i titoli vicino alle scritte già presenti nelle immagini: possono esserci ripetizioni. Contenuti e visibilità hanno superato i controlli.'
            meta['poster_reference_cosmetic_warnings']=issues
            return html
        if attempt==2:raise ValueError('Locandina non completata: restano contenuti mancanti o coperti dopo due correzioni automatiche. La bozza e la diagnosi sono conservate nel canvas.')
        stage('Locandine · correggo automaticamente i problemi di impaginazione')
        repair=request+[{'role':'assistant','content':html},{'role':'user','content':'La verifica CPU della pagina ha trovato questi problemi reali: '+json.dumps(issues,ensure_ascii=False)+'. Riscrivi l’HTML/CSS completo correggendoli. Conserva struttura semantica, tutte le immagini e tutti i dati del riferimento. Non stampare diagnosi. Per testi coperti o tagliati, riorganizza il flusso e riserva spazio al footer: non ridurre tutto a caratteri minuscoli. Non nascondere elementi per superare il controllo. La figura principale deve restare un visual importante, non una miniatura. Niente dati inventati.'}]
        html=generate(app.engine,repair,settings,cancel,stream,stage,'Locandina · correzione automatica',require_style=True)
