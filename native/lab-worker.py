"""Render trusted declarative scenes; generated Python is never executed."""
import json,os,sys,math,ast,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/lab'),str(ROOT/'native/vendor')]
os.environ['MPLBACKEND']='Agg';os.environ['MPLCONFIGDIR']=str(ROOT/'runtime/tools/lab-cache');os.environ['PYGLET_HEADLESS']='true'
dll=os.add_dll_directory(str(ROOT/'runtime/tools/lab')) if os.name=='nt' and (ROOT/'runtime/tools/lab').is_dir() else None
from h3chat.lab import validate_scene
from h3chat.calculator import Calculator
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()
def render(spec,folder,opts):
    spec=validate_scene(spec);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    from manim import Scene,Text,Circle,Rectangle,Arrow,Axes,SVGMobject,Create,Write,FadeIn,tempconfig
    from matplotlib.mathtext import math_to_image
    import numpy as np
    class Artifact(Scene):
        def construct(self):
            frames=spec.get('scenes',[spec]);duration=opts['duration']/len(frames)
            for frame_no,frame in enumerate(frames):
                self.clear()
                for i,obj in enumerate(frame['objects']):
                    emit('stage',message=f'Manim · scena {frame_no+1}/{len(frames)} · oggetto {i+1}/{len(frame["objects"])}');kind=obj['type'];color=obj.get('color','#24605b');p=[obj.get('x',0),obj.get('y',0),0]
                    if kind=='text':m=Text(obj['text'],font='Arial',font_size=30,color=color);m.scale(min(1,12/max(.01,m.width),6/max(.01,m.height))).move_to(p)
                    elif kind=='formula':
                        svg=folder/f'formula-{frame_no}-{i}.svg';math_to_image('$'+obj['text'].strip('$')+'$',svg,format='svg',color=color,dpi=160);m=SVGMobject(str(svg));m.scale(min(1,10/max(.01,m.width))).move_to(p)
                        if opts.get('device')=='gpu':
                            # SVGMobject assigns a scalar on its OpenGL root; interpolation needs arrays.
                            for part in m.get_family():
                                if isinstance(getattr(part,'stroke_width',None),(int,float)):part.set_stroke(width=part.stroke_width,recurse=False)
                    elif kind=='circle':m=Circle(radius=obj.get('radius',1),color=color).move_to(p)
                    elif kind=='rectangle':m=Rectangle(width=obj.get('width',2),height=obj.get('height',1),color=color).move_to(p)
                    elif kind=='arrow':m=Arrow([*obj['start'],0],[*obj['end'],0],color=color,buff=0)
                    elif kind=='plot':
                        lo,hi=obj.get('x_min',-3),obj.get('x_max',3);bottom,top=obj.get('y_min',0),obj.get('y_max',9)
                        axes=Axes(x_range=[lo,hi,(hi-lo)/6],y_range=[bottom,top,(top-bottom)/5],x_length=9,y_length=5,axis_config={'color':'#536c64','include_tip':False}).move_to(p)
                        calc=Calculator();tree=ast.parse(obj['expression'],mode='eval').body;points=[]
                        for x in np.linspace(lo,hi,201):calc.values['x']=float(x);y=calc.expr(tree);points.append(axes.c2p(float(x),float(y)))
                        from manim import VMobject,VGroup
                        from manim.mobject.opengl.opengl_vectorized_mobject import OpenGLVMobject
                        curve=(OpenGLVMobject if opts.get('device')=='gpu' else VMobject)(color=color);curve.set_points_as_corners(points)
                        labels=VGroup()
                        for x in np.linspace(lo,hi,7):
                            labels.add(Text(f'{x:g}',font='Arial',font_size=15,color='#536c64').next_to(axes.c2p(float(x),bottom),[0,-1,0],buff=.1))
                        for y in np.linspace(bottom,top,6):
                            labels.add(Text(f'{y:g}',font='Arial',font_size=15,color='#536c64').next_to(axes.c2p(lo,float(y)),[-1,0,0],buff=.1))
                        m=VGroup(axes,curve,labels)
                    appear=(FadeIn(m) if opts.get('device')=='gpu' else Write(m)) if kind in ('text','formula') else Create(m)
                    self.play(appear,run_time=min(.8,duration*.75/len(frame['objects'])))
                self.wait(max(.1,duration-min(.8,duration*.75/len(frame['objects']))*len(frame['objects'])))
    with tempconfig({'media_dir':str(folder),'output_file':'animation','pixel_width':opts['width'],'pixel_height':opts['height'],'frame_rate':opts['fps'],'renderer':'opengl' if opts.get('device')=='gpu' else 'cairo','background_color':'#fcfbf7','disable_caching':True,'write_to_movie':True,'verbosity':'ERROR'}):
        scene=Artifact();scene.render();return str(Path(scene.renderer.file_writer.movie_file_path).resolve())
emit('hello',engine='lab')
for line in sys.stdin:
    try:
        req=json.loads(line);path=render(req['scene'],req['output'],req['options']);emit('result',result={'path':path})
    except Exception as e:traceback.print_exc();emit('error',message=str(e))
