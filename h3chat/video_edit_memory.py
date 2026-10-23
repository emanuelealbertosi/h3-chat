"""Reconstruct native visual memory from the selected timeline's saved footage."""
from .downloads import safe_join


def source_indices(record, index):
    """Stop at the last preceding intentional cut; never use future footage."""
    if not 0 < index < len(record['timeline']):
        raise ValueError('La prima clip non ha una memoria precedente da recuperare.')
    anchor=max((i for i in range(index) if record['timeline'][i].get('continuity')=='cut'),default=0)
    recent=list(range(max(anchor,index-2),index))
    return anchor,recent


def describe(record, index):
    scene=record['timeline'][index]
    return {'available':index>0,'default':index>0 and bool(scene.get('recover_memory',scene.get('continuity')=='continue')),
            'cut':scene.get('continuity')=='cut'}


def validate(patch, scene, index):
    enabled=patch.get('recover_memory',False)
    if type(enabled) is not bool:
        raise ValueError('Memoria precedente: scegli attiva o disattiva.')
    if not enabled:return
    if index==0:
        raise ValueError('La prima clip non ha una memoria precedente da recuperare.')
    if patch.get('mode','reference')!='reference':
        raise ValueError('Il recupero memoria richiede Rigenera · riferimenti; Modifica video e I2V usano le proprie guide.')
    if patch.get('start',0)!=0 or patch.get('end',scene['duration'])!=scene['duration']:
        raise ValueError('Il recupero memoria richiede Intera clip; per un tratto usa i fotogrammi guida.')


def restore(data, record, index):
    anchor,recent=source_indices(record,index)
    def path(position):
        sources=record.get('clip_sources')
        if sources is not None and sources[position] is not None:
            raise ValueError('Un tratto della memoria non è ancora stato preparato.')
        file=safe_join(data,record['outputs'][position])
        try:
            with file.open('rb') as source:
                if source.read(12)[4:8]!=b'ftyp':raise ValueError('Un video della memoria non è un MP4 valido.')
        except OSError as exc:
            raise ValueError('Una clip precedente necessaria alla memoria non è più disponibile.') from exc
        return str(file)
    return {'opening':path(anchor),'recent':[path(i) for i in recent]}, {'opening_clip':anchor+1,'recent_clips':[i+1 for i in recent]}
