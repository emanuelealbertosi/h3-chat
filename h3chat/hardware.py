"""Read-only hardware discovery and conservative, per-engine memory estimates."""
from __future__ import annotations
import csv
import ctypes as C
import io
import os
import platform
import subprocess
import threading
import time
import uuid

GIB=1024**3
MIB=1024**2
_lock=threading.Lock()
_cache=None


def windows_memory():
    class Memory(C.Structure):
        _fields_=[('length',C.c_ulong),('load',C.c_ulong)]+[(k,C.c_ulonglong) for k in
            ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
    value=Memory(); value.length=C.sizeof(value)
    if not C.windll.kernel32.GlobalMemoryStatusEx(C.byref(value)): raise OSError('RAM non disponibile')
    return {'total_mb':value.total/MIB,'free_mb':value.available/MIB,'commit_free_mb':value.page_available/MIB}


def windows_adapters():
    class Luid(C.Structure): _fields_=[('low',C.c_uint),('high',C.c_int)]
    class Desc(C.Structure):
        _fields_=[('name',C.c_wchar*128),('vendor',C.c_uint),('device',C.c_uint),('subsys',C.c_uint),
            ('revision',C.c_uint),('dedicated',C.c_size_t),('system',C.c_size_t),('shared',C.c_size_t),
            ('luid',Luid),('flags',C.c_uint)]
    def call(obj,slot,restype,*types):
        table=C.cast(obj,C.POINTER(C.POINTER(C.c_void_p))).contents
        return C.WINFUNCTYPE(restype,C.c_void_p,*types)(table[slot])
    factory=C.c_void_p(); iid=(C.c_ubyte*16).from_buffer_copy(uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le)
    create=C.windll.dxgi.CreateDXGIFactory1
    create.argtypes=[C.c_void_p,C.POINTER(C.c_void_p)]; create.restype=C.c_long
    if create(C.byref(iid),C.byref(factory))<0: return []
    result=[]
    try:
        for index in range(32):
            adapter=C.c_void_p()
            if call(factory,12,C.c_long,C.c_uint,C.POINTER(C.c_void_p))(factory,index,C.byref(adapter))<0: break
            try:
                desc=Desc()
                if call(adapter,10,C.c_long,C.POINTER(Desc))(adapter,C.byref(desc))>=0 and not desc.flags&2:
                    result.append({'name':desc.name,'vendor':{0x10de:'NVIDIA',0x1002:'AMD',0x8086:'Intel'}.get(desc.vendor,'GPU'),
                        'total_mb':desc.dedicated/MIB,'shared_mb':desc.shared/MIB,'free_mb':None,'source':'DXGI',
                        'luid':f'luid_0x{desc.luid.high & 0xffffffff:08x}_0x{desc.luid.low:08x}'})
            finally: call(adapter,2,C.c_ulong)(adapter)
    finally: call(factory,2,C.c_ulong)(factory)
    return result


def detect_hardware(refresh=False):
    global _cache
    with _lock:
        if _cache and not refresh and time.time()-_cache['checked_at']<10: return _cache
        result={'cpu_name':platform.processor() or platform.machine(),'cpu_threads':os.cpu_count() or 1,
                'ram':{'total_mb':None,'free_mb':None},'gpu':[],'checked_at':time.time(),
                'note':'Stime preventive, non garanzie. La memoria libera cambia con le altre applicazioni; la RAM condivisa non è VRAM dedicata.'}
        if os.name=='nt':
            try: result['ram']=windows_memory()
            except (OSError,AttributeError): pass
            try: result['gpu']=windows_adapters()
            except (OSError,AttributeError,ValueError): pass
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                    result['cpu_name']=winreg.QueryValueEx(key,'ProcessorNameString')[0].strip()
            except OSError: pass
        else:
            try:
                with open('/proc/meminfo') as f: mem={l.split(':')[0]:int(l.split()[1])/1024 for l in f}
                result['ram']={'total_mb':mem['MemTotal'],'free_mb':mem['MemAvailable']}
            except (OSError,ValueError,KeyError): pass
        flags=0x08000000 if os.name=='nt' else 0
        try:
            raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],
                timeout=4,creationflags=flags,stderr=subprocess.DEVNULL).decode('utf-8','replace')
            used=set(); nvidia=[]
            for row in csv.reader(io.StringIO(raw)):
                name,total,free=(s.strip() for s in row)
                gpu=next((g for g in result['gpu'] if g['name'].strip()==name and id(g) not in used),None)
                if gpu is None:
                    gpu={'name':name,'vendor':'NVIDIA','shared_mb':0};result['gpu'].append(gpu)
                gpu.update(total_mb=float(total),free_mb=float(free),source='nvidia-smi');used.add(id(gpu));nvidia.append(gpu)
            if nvidia:
                result['gpu']=[g for g in result['gpu'] if g.get('vendor')!='NVIDIA']+nvidia
        except (OSError,ValueError,subprocess.SubprocessError): pass
        # WDDM adapter counters cover AMD/Intel when exposed by the installed driver.
        if os.name=='nt' and any(g['free_mb'] is None for g in result['gpu']):
            try:
                import json
                raw=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                    'Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | Select-Object Name,DedicatedUsage | ConvertTo-Json -Compress'],
                    timeout=5,creationflags=flags,stderr=subprocess.DEVNULL).decode('utf-8','replace')
                rows=json.loads(raw);rows=rows if isinstance(rows,list) else [rows]
                for gpu in result['gpu']:
                    matching=[r for r in rows if r and gpu.get('luid','missing').lower() in r.get('Name','').lower()]
                    if gpu['free_mb'] is None and matching and gpu['total_mb']>512:
                        gpu['free_mb']=max(0,gpu['total_mb']-sum(int(r['DedicatedUsage']) for r in matching)/MIB)
                        gpu['source']='DXGI + WDDM'
            except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError): pass
        _cache=result
        return result


def assess_model(model, settings, hardware, references=1):
    """Estimate one loaded context and its inference workspace, for the selected placement."""
    chat='chat' in model['capabilities']; files=model['files']; p=model.get('parameters',{})
    sizes={role:sum(f['size']/GIB for f in files if f['role']==role) for role in {f['role'] for f in files}}
    projector=sizes.get('mmproj',0)
    if model.get('vision',{}).get('projector_size'): projector=model['vision']['projector_size']/GIB
    elif model.get('ready') and not model.get('vision',{}).get('enabled'): projector=0
    weights=sum(sizes.values())-sizes.get('mmproj',0)
    backend='cpu' if settings['profile']=='cpu' else settings['backend']
    resident=settings.get('memory_policy')=='resident'
    gpus=[g for g in hardware['gpu'] if backend!='cuda' or g.get('vendor')=='NVIDIA']
    # Do not add different GPUs together or claim an unverified device selection.
    gpu=gpus[0] if len(gpus)==1 else None
    ram=hardware['ram']; free_ram=(ram.get('free_mb') or 0)/1024
    assumptions=[]; patches={}; risk=False
    if chat:
        known={'qwen3-06':(28,1024,16,8,128),'qwen3-4':(36,2560,32,8,128),'qwen25-vl3':(36,2048,16,2,128),'smolvlm':(32,960,15,5,64)}
        default=known.get(model['id'],(32,4096,32,8,128))
        layers=p.get('layers') or default[0]; heads=p.get('heads') or default[2]
        emb=p.get('embedding') or default[1]; kv_heads=p.get('kv_heads') or default[3]
        kd=p.get('key_length') or (emb//heads if p.get('embedding') else default[4]);vd=p.get('value_length') or kd
        kv=settings['context']*layers*kv_heads*(kd+vd)*2/GIB
        frac=(1 if resident else min(1,settings['gpu_layers']/(layers+1))) if backend!='cpu' else 0
        vision=projector>0 or model.get('vision',{}).get('expected',False)
        workspace=.65+(references*.2*settings['context']/4096 if vision else 0)
        all_gpu=weights*1.15+kv
        vram=all_gpu*frac+(.45 if frac else 0)
        needed_ram=weights*(1-frac)*1.15+weights*.15+projector*1.2+kv*(1-frac)+workspace
        if resident and backend!='cpu':
            vram+=projector*1.2+workspace
            needed_ram=max(.5,needed_ram-projector*1.2)
        cpu_ram=weights*1.3+projector*1.2+kv+workspace
        if not p.get('layers'): assumptions.append('KV cache stimata dai parametri del catalogo o da valori conservativi; sarà affinata dopo il download.')
        if frac<1 and backend!='cpu': assumptions.append('Parte dei layer resta in RAM con le impostazioni attuali.')
    else:
        main=sizes.get('diffusion',sizes.get('model',0))
        companions=weights-main
        pixels=settings['width']*settings['height']/(512*512)
        workspace=(1.4 if model.get('architecture')=='sd' else 2.5)*pixels**.7+references*.3
        vram=main*1.15+workspace if backend!='cpu' else 0
        needed_ram=weights*1.25+2 if backend!='cpu' else weights*1.3+workspace+1
        if resident and backend!='cpu':
            vram=weights*1.25+workspace
            needed_ram=weights*.15+1
        cpu_ram=weights*1.3+workspace+1
        frac=1
        assumptions.append('Picco immagini stimato da pesi, risoluzione e riferimenti. '+('Pesi, VAE ed encoder restano sulla GPU.' if resident and backend!='cpu' else 'Pesi in RAM recuperati dalla GPU a segmenti; VAE ed encoder usano la CPU.' if backend!='cpu' else 'Tutti i componenti usano la RAM.'))
    status='ok'; title='OK stimato'; advice='La configurazione sembra rientrare nella memoria libera, con un margine di sicurezza.'
    if ram.get('free_mb') is None:
        status='unknown';title='Memoria non rilevata';advice='Impossibile valutare il rischio OOM senza conoscere la RAM libera.'
    elif needed_ram>max(0,free_ram-.75):
        status='oom';title='Rischio OOM';risk=True
        advice='La RAM libera è inferiore alla stima. Chiudi altre applicazioni o scegli un modello, contesto o risoluzione più piccoli.'
    if backend!='cpu':
        if not gpus:
            status='unknown';title='GPU compatibile non rilevata';advice='Verifica driver e backend oppure scegli Solo CPU.';patches={'profile':'cpu','backend':'cpu','gpu_layers':0}
        elif gpu is None:
            status='unknown';title='Più GPU rilevate';advice='Le memorie delle GPU non vengono sommate. La scelta automatica del motore impedisce una stima affidabile per dispositivo.'
        elif gpu.get('free_mb') is None or gpu.get('total_mb',0)<=512:
            if status!='oom': status='unknown';title='VRAM libera non misurabile';advice='Rilevata GPU, ma il driver non espone memoria dedicata libera affidabile. La memoria condivisa usa la RAM.'
        elif vram>max(0,gpu['free_mb']/1024-.5):
            risk=True
            if cpu_ram<=max(0,free_ram-.75):
                status='offload';title='Offload necessario'
                if chat:
                    fit=max(0,int(max(0,gpu['free_mb']/1024-.95)/all_gpu*(layers+1)))
                    patches={'gpu_layers':min(fit,settings['gpu_layers'])}
                    if resident: patches['memory_policy']='on_demand'
                    advice=f'Con i layer attuali rischi OOM sulla GPU. Riduci a circa {patches["gpu_layers"]} layer GPU; il resto userà la RAM.'
                else:
                    patches={'profile':'cpu','backend':'cpu','gpu_layers':0}
                    advice='La VRAM libera non basta alla stima. Offload e tiling sono già attivi: usa CPU o un modello/risoluzione più piccoli.'
            else:
                status='oom';title='Rischio OOM';advice='La VRAM non basta e neppure la RAM libera offre spazio sufficiente per un passaggio completo alla CPU.'
        elif status=='ok' and chat and frac<1:
            status='offload';title='Offload previsto';advice='I layer selezionati entrano nella VRAM stimata; i rimanenti usano la RAM e rallentano la risposta.'
    return {'id':model['id'],'name':model['name'],'status':status,'title':title,'advice':advice,
            'oom_risk':risk,'ram_gb':round(needed_ram,2),'vram_gb':round(vram,2),'cpu_ram_gb':round(cpu_ram,2),
            'gpu_name':gpu['name'] if gpu else None,'assumptions':assumptions,'recommended_patch':patches}


def assess_selection(models, settings, hardware, references=1):
    """Conservative peak sum for resident contexts; maximum for serial on-demand use.

    Shared create/edit weights identify one context; distinct models keep their own
    companions because native contexts cannot share tensor allocations.
    """
    unique = {}
    for model in models:
        kind = 'chat' if 'chat' in model['capabilities'] else 'image'
        key = (kind,tuple(sorted((f['role'],f['path']) for f in model['files'])))
        unique[key] = model
    values = [assess_model(m,settings,hardware,references) for m in unique.values()]
    resident = settings.get('memory_policy')=='resident'
    combine = sum if resident else lambda values:max(values,default=0)
    ram = round(combine(v['ram_gb'] for v in values),2)
    vram = round(combine(v['vram_gb'] for v in values),2)
    backend = 'cpu' if settings['profile']=='cpu' else settings['backend']
    gpus = [g for g in hardware['gpu'] if backend!='cuda' or g.get('vendor')=='NVIDIA']
    free_ram = hardware['ram'].get('free_mb')
    status,title,advice = 'ok','OK stimato','I modelli scelti sembrano rientrare nella memoria libera.'
    if free_ram is None or (backend!='cpu' and (len(gpus)!=1 or gpus[0].get('free_mb') is None)):
        status,title,advice = 'unknown','Non determinabile','La memoria libera non è misurabile con sufficiente affidabilità.'
    elif ram>max(0,free_ram/1024-.75) or (backend!='cpu' and vram>max(0,gpus[0]['free_mb']/1024-.5)):
        status,title,advice = 'oom','Rischio OOM complessivo','La memoria libera non basta alla stima complessiva. '+('Passa ad A richiesta o scegli modelli più piccoli.' if resident else 'Riduci modello, contesto o risoluzione; valuta CPU o meno layer GPU.')
    elif any(v['status']=='offload' for v in values):
        status,title,advice = 'offload','Offload previsto','Alcuni componenti restano in RAM con le impostazioni attuali.'
    return {'status':status,'title':title,'advice':advice,'ram_gb':ram,'vram_gb':vram,'unique_models':len(unique),
            'policy':settings.get('memory_policy','on_demand'),
            'note':('Somma prudente dei picchi dei modelli distinti; crea ed edit con gli stessi pesi contano una volta.' if resident else 'Picco massimo dei modelli distinti: viene conservato un solo contesto alla volta.')}
