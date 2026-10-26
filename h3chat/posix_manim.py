"""CPU Manim with generated Python confined by the native POSIX sandbox."""
import json
import os
from pathlib import Path
import shutil
import tempfile


def render(root,request,stage):
    from .manim_code import validate_source
    from .platform_runtime import python_executable
    from .posix_computer import run
    root=Path(root);source=validate_source(request['source'])
    output=Path(request['output']).resolve();output.mkdir(parents=True,exist_ok=True)
    jobs=root/'runtime/manim-jobs';jobs.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='posix-',dir=jobs) as temporary:
        folder=Path(temporary);assets=folder/'assets';assets.mkdir()
        if len(request.get('assets',[]))>12:raise ValueError('Manim: massimo 12 allegati.')
        for asset in request.get('assets',[]):
            name=asset['name'];path=Path(asset['path']).resolve()
            if Path(name).name!=name or len(name)>120 or not path.is_file() or path.stat().st_size>64*1024**2:raise ValueError('Allegato Manim non valido.')
            shutil.copyfile(path,assets/name)
        options=dict(request['options']);options['device']='cpu'
        presentation=request.get('presentation')
        if presentation and presentation.get('background') not in [a['name'] for a in request.get('assets',[])]:raise ValueError('Sfondo Manim non disponibile.')
        (folder/'scene.py').write_text(source['code'],encoding='utf8')
        (folder/'request.json').write_text(json.dumps({'scene_name':source['scene_name'],'options':options,'presentation':presentation}),encoding='utf8')
        for name in ('temp','cache'): (folder/name).mkdir()
        env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(folder),'USERPROFILE':str(folder),'TMPDIR':str(folder/'temp'),
             'MPLCONFIGDIR':str(folder/'cache'),'MPLBACKEND':'Agg','PYGLET_HEADLESS':'true','LANG':'en_US.UTF-8'}
        latex=root/'runtime/tools/latex/TinyTeX'
        bins=sorted((latex/'bin').glob('*')) if (latex/'bin').exists() else []
        if bins:env['PATH']=str(bins[0])+':'+env['PATH']
        stdin=folder/'stdin';stdin.touch();log=folder/'render.log'
        reads=[root/'runtime/tools/lab',root/'runtime/tools/documents',latex,root/'native/manim-runner.py',root/'native/vendor',root/'native/slide_geometry.py']
        stage('Manim · CPU · processo isolato')
        code=run(root,[python_executable(root),'-I','-X','utf8',root/'native/manim-runner.py'],folder,env,stdin,log,options.get('timeout',600),sandbox=folder,reads=reads)
        (output/'manim-render.log').write_text(log.read_text(encoding='utf8',errors='replace')[-20000:],encoding='utf8')
        if code:raise ValueError('Manim: rendering fallito. '+log.read_text(encoding='utf8',errors='replace')[-2500:])
        result=json.loads((folder/'result.json').read_text());path=Path(result['path']).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or path.stat().st_size>512*1024**2:raise ValueError('Output Manim non valido.')
        target=output/'animation.mp4';shutil.copyfile(path,target)
        import sys
        sys.path.insert(0,str(root/'runtime/tools/documents'))
        import av
        with av.open(str(target)) as movie:duration=float(movie.duration/av.time_base)
        tex=[]
        for i,path in enumerate(sorted((folder/'media').rglob('*.tex'))[:30]):
            if path.resolve().is_relative_to(folder) and path.stat().st_size<1024**2:
                dest=output/f'formula-{i+1}.tex';shutil.copyfile(path,dest);tex.append(str(dest))
        return {'path':str(target),'duration':duration,'latex':tex,'sandbox':'POSIX · cartella isolata · rete disabilitata'}
