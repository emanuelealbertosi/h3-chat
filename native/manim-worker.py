"""Trusted broker for full Python Manim; source executes only in AppContainer."""
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.manim_code import validate_source
from h3chat.windows_sandbox import run
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**values):wire.write(json.dumps({'event':event,**values},ensure_ascii=False)+'\n');wire.flush()

def render(request):
    source=validate_source(request['source']);output=Path(request['output']).resolve();output.mkdir(parents=True,exist_ok=True)
    folder=ROOT/'runtime/manim-jobs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    tickets=folder.parent/'.tickets';tickets.mkdir(exist_ok=True)
    ticket=tickets/(folder.name+'.json');ticket.write_text(json.dumps({'owner':os.getpid()}),encoding='utf-8')
    assets=folder/'assets';assets.mkdir()
    if len(request.get('assets',[]))>12:raise ValueError('Manim: massimo 12 allegati.')
    for asset in request.get('assets',[]):
        name=asset['name']
        if Path(name).name!=name or len(name)>120:raise ValueError('Nome allegato Manim non valido.')
        path=Path(asset['path']).resolve()
        if not path.is_file() or path.stat().st_size>64*1024**2:raise ValueError('Allegato Manim non disponibile o oltre 64 MB.')
        shutil.copyfile(path,assets/name)
    opts=request['options']
    (folder/'scene.py').write_text(source['code'],encoding='utf-8')
    presentation=request.get('presentation')
    if presentation and (not isinstance(presentation,dict) or presentation.get('background') not in [a['name'] for a in request.get('assets',[])]):raise ValueError('Sfondo della slide non disponibile.')
    if presentation and presentation.get('geometry') in (1,2):
        from native.slide_geometry import SlideSpace,validate_annotations
        SlideSpace(opts['frame_width'],opts['frame_height'],1,presentation.get('anchors',[]))
        if presentation['geometry']==1:validate_annotations(source['code'])
    (folder/'request.json').write_text(json.dumps({'scene_name':source['scene_name'],'options':opts,'presentation':presentation}),encoding='utf-8')
    system=os.environ.get('SystemRoot',r'C:\Windows')
    latex=ROOT/'runtime/tools/latex/TinyTeX/bin/windows'
    environment={'SystemRoot':system,'WINDIR':system,'PATH':str(latex)+os.pathsep+str(Path(system)/'System32'),
        'TEMP':str(folder/'temp'),'TMP':str(folder/'temp'),'USERPROFILE':str(folder),'APPDATA':str(folder/'cache'),
        'LOCALAPPDATA':str(folder/'cache'),'PYGLET_HEADLESS':'true','MPLBACKEND':'Agg'}
    import ctypes as C
    from ctypes import wintypes as W
    k=C.WinDLL('kernel32',use_last_error=True)
    k.QueryDosDeviceW.argtypes=[W.LPCWSTR,W.LPWSTR,W.DWORD];k.QueryDosDeviceW.restype=W.DWORD
    devices={}
    for drive in {ROOT.drive,system[:2]}:
        buffer=C.create_unicode_buffer(32768)
        if not k.QueryDosDeviceW(drive,buffer,len(buffer)):raise C.WinError(C.get_last_error())
        devices[drive]=buffer.value
    environment['H3_DRIVE_MAP']=json.dumps(devices)


    (folder/'temp').mkdir();(folder/'cache').mkdir()
    emit('stage',message='Manim completo · rendering '+('3D / 2D GPU' if opts['device']=='gpu' else '3D / 2D CPU'))
    # User-approved temporary alias of this app folder; file ACLs are unchanged.
    # TeX's legacy short-name lookup then stays inside the permitted root.
    import subprocess
    drive=next((chr(i)+':' for i in range(90,67,-1) if not Path(chr(i)+':/').exists()),None)
    if not drive:raise ValueError('LaTeX: nessuna lettera libera per la cartella temporanea.')
    mapped=False
    try:
        ticket.write_text(json.dumps({'owner':os.getpid(),'drive':drive}),encoding='utf-8')
        subprocess.run(['subst',drive,str(ROOT)],check=True,capture_output=True,creationflags=0x08000000);mapped=True
        environment['PATH']=drive+r'\runtime\tools\latex\TinyTeX\bin\windows'+os.pathsep+str(Path(system)/'System32')
        devices[drive]=devices[ROOT.drive]+str(ROOT)[2:];environment['H3_DRIVE_MAP']=json.dumps(devices)
        code=run(ROOT,folder,[ROOT/'runtime/python/python.exe','-I','-X','utf8',ROOT/'native/manim-runner.py'],environment,
            timeout=opts.get('timeout',600),memory_gb=opts.get('memory_gb',4))
        log=(folder/'render.log').read_text(encoding='utf-8',errors='replace')[-20000:]
        (output/'manim-render.log').write_text(log,encoding='utf-8')
        if code:
            if code==0xc0000017:raise ValueError('Manim: memoria insufficiente. Aumenta il limite nelle Preferenze.')
            raise ValueError('Rendering Manim non riuscito.\n'+log[-6000:])
        result=json.loads((folder/'result.json').read_text(encoding='utf-8'));path=Path(result['path']).resolve()
        if not path.is_relative_to(folder) or not path.is_file():raise ValueError('Video Manim non disponibile nella cartella isolata.')
        if path.stat().st_size>512*1024**2:raise ValueError('Video Manim oltre il limite di 512 MB.')
        with path.open('rb') as stream:
            if stream.read(12)[4:8]!=b'ftyp':raise ValueError('Manim non ha prodotto un MP4 valido.')
        target=output/'animation.mp4';shutil.copyfile(path,target)
        tex=[]
        for index,path in enumerate(sorted((folder/'media').rglob('*.tex'))[:30]):
            if path.is_file() and path.resolve().is_relative_to(folder) and path.stat().st_size<1024**2:
                target_tex=output/f'formula-{index+1}.tex';shutil.copyfile(path,target_tex);tex.append(str(target_tex))
        sys.path.insert(0,str(ROOT/'runtime/tools/lab'))
        dll=os.add_dll_directory(str(ROOT/'runtime/tools/lab'))
        import av
        with av.open(str(target)) as movie:
            stream=movie.streams.video[0];duration=float(stream.duration*stream.time_base) if stream.duration is not None else float(movie.duration/av.time_base)
        return {'path':str(target),'duration':duration,'latex':tex,'sandbox':'Windows AppContainer · nessuna capacità rete'}
    finally:
        removed=not mapped or subprocess.run(['subst',drive,'/D'],capture_output=True,creationflags=0x08000000).returncode==0
        if removed and not (ticket.exists() and json.loads(ticket.read_text()).get('cleanup_pending')):ticket.unlink(missing_ok=True)
        if (folder/'render.log').exists():
            (output/'manim-render.log').write_text((folder/'render.log').read_text(encoding='utf-8',errors='replace')[-20000:],encoding='utf-8')
        # Only this broker-owned UUID folder, after descendants are terminated.
        if folder.resolve().is_relative_to(ROOT/'runtime/manim-jobs'):shutil.rmtree(folder,ignore_errors=True)

emit('hello',engine='manim')
for line in sys.stdin:
    try:emit('result',result=render(json.loads(line)))
    except Exception as e:traceback.print_exc();emit('error',message=str(e))
