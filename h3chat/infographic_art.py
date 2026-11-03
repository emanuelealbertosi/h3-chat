"""Carry the approved art direction and assigned illustrations into every shot."""
import re


def requested_logo(prompt,input_media,count):
    # Only the single input explicitly called a logo by the owner is unambiguous.
    # Do not guess among several attachments without a real caption/selection.
    images=[m for m in input_media if m.get('mime','').startswith('image/')]
    if len(images)!=1 or not re.search(r'\b(?:usa\w*|inserisci|aggiungi|mostra|applica)\b[^.!?\n]{0,35}\blogo\b[^.!?\n]{0,45}\ballegat[oa]\b',prompt,re.I):return []
    last=bool(re.search(r'\b(?:solo in chiusura|solo alla fine|nell[’\x27]ultima scena)\b',prompt,re.I))
    return [{'scene':count if last else 1,'asset_id':images[0]['id'],'role':'logo',
             'description':'Logo originale: unico allegato indicato dall’utente. Usa imageFit contain, non ridisegnarlo o sostituirlo; mantienilo leggibile e non invasivo.'}]


def scene_request(plan,index,image_plan,required=()):
    row=dict(plan['scenes'][index])
    row['visual_direction']=plan['visual_direction']
    row['illustrations']=[{k:item[k] for k in ('asset_id','description','aspect','width','height') if k in item}
                         for item in image_plan if item.get('slide')==index+1 and item.get('asset_id')]
    row['illustrations'] += [{k:v for k,v in item.items() if k!='scene'} for item in required if item['scene']==index+1]
    row['continuity']={'previous':plan['scenes'][index-1]['purpose'] if index else '',
                       'next':plan['scenes'][index+1]['purpose'] if index+1<len(plan['scenes']) else '',
                       'direction':'Mantieni palette, stile, luce e personaggi coerenti fra le inquadrature. Progetta entrata e uscita per raccordarsi allo zoom/dissolvenza del montaggio; non ripartire con una grafica scollegata.'}
    return row
