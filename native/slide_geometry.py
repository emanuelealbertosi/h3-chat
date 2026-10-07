"""Measured slide coordinates shared by the planner and isolated Manim renderer."""
import ast
import math


class GeometryError(ValueError):pass


def anchors(page):
    result=[{'id':'slide','kind':'slide','text':'Intera slide','left':0,'top':0,'width':1,'height':1}]
    counts={}
    for region in page.get('anchors',page.get('regions',[])):
        kind=region.get('kind','image');counts[kind]=counts.get(kind,0)+1
        row={k:region[k] for k in ('left','top','width','height')}
        row.update(id=region.get('id',f'{kind}-{counts[kind]:03}'),kind=kind,text=region.get('text','')[:1500])
        if 'asset' in region:row['asset']=region['asset']
        result.append(row)
    return result


def validate_annotations(code):
    """Reject pixel-based shapes and moving measured annotations off their anchors.

    This is a layout contract, not the Python security boundary (AppContainer).
    Full scene code, animation APIs, loops and updaters remain available.
    """
    tree=ast.parse(code);aliases={};anchored=set()
    constructors={'Rectangle','RoundedRectangle','Square','Circle','Ellipse','Arrow','Line','SurroundingRectangle'}
    methods={'box','ellipse','underline','pointer'}
    geometry={'move_to','shift','scale','stretch','set_x','set_y','set_width','set_height','set_points','rotate','next_to','to_edge','to_corner','align_to'}
    def root(node):
        while isinstance(node,ast.Attribute):node=node.value
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='slide' and node.func.attr in methods:return '__anchor__'
            return root(node.func)
        return node.id if isinstance(node,ast.Name) else None
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):
            aliases.update({a.asname or a.name:a.name for a in node.names})
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            value=node.value;targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            if root(value)=='__anchor__':anchored.update(t.id for t in targets if isinstance(t,ast.Name))
    # Follow simple aliases so e.g. another = highlight cannot bypass the check.
    for _ in range(3):
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and root(node.value) in anchored:anchored.update(t.id for t in node.targets if isinstance(t,ast.Name))
    for node in ast.walk(tree):
        if isinstance(node,ast.ClassDef) and any((isinstance(b,ast.Name) and aliases.get(b.id,b.id) in ('ThreeDScene','MovingCameraScene')) for b in node.bases):
            raise GeometryError('Mantieni layout: usa Scene con camera fissa; per ricostruzioni e camera 3D scegli Ricostruisci.')
        if not isinstance(node,ast.Call):continue
        name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
        if aliases.get(name,name) in constructors:
            raise GeometryError('Mantieni layout: crea evidenziazioni con slide.box(id), slide.ellipse(id), slide.underline(id) o slide.pointer(id). Non costruire forme con dimensioni o coordinate inventate/pixel.')
        if isinstance(node.func,ast.Attribute) and node.func.attr in geometry and root(node.func.value) in anchored|{'__anchor__'}:
            raise GeometryError('Le evidenziazioni misurate sono già posizionate: non spostarle, scalarle o ridimensionarle. Usa Create, FadeIn, FadeOut, Indicate, colori e opacità per animarle.')
        if name in ('move_camera','set_camera_orientation','begin_ambient_camera_rotation') or (isinstance(node.func,ast.Attribute) and name in geometry and any(isinstance(n,ast.Attribute) and n.attr=='camera' for n in ast.walk(node.func.value))):
            raise GeometryError('Mantieni layout richiede la camera fissa per conservare l’allineamento con la slide.')


class SlideSpace:
    def __init__(self,width,height,aspect,regions=()):
        for v in (width,height,aspect):
            if type(v) not in (int,float) or not math.isfinite(v) or v<=0:raise GeometryError('Dimensioni della slide non valide.')
        self.frame_width=width;self.frame_height=height
        self.slide_width=min(width,height*aspect);self.slide_height=self.slide_width/aspect
        self.regions={}
        for region in regions:
            name=region['id']
            if name in self.regions:raise GeometryError('Riferimento slide duplicato.')
            values=[region[k] for k in ('left','top','width','height')]
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise GeometryError('Coordinate della slide non valide.')
            x,y,w,h=values
            if x<0 or y<0 or w<=0 or h<=0 or x+w>1.000001 or y+h>1.000001:raise GeometryError('Riferimento fuori dalla slide.')
            self.regions[name]=dict(region)

    def region(self,name):
        if isinstance(name,(list,tuple)):
            if not name:raise GeometryError('Indica almeno un riferimento misurato.')
            rows=[self.region(n) for n in name]
            l=min(r['left'] for r in rows);t=min(r['top'] for r in rows)
            return {'left':l,'top':t,'width':max(r['left']+r['width'] for r in rows)-l,
                    'height':max(r['top']+r['height'] for r in rows)-t}
        if name not in self.regions:raise GeometryError('Riferimento slide sconosciuto: '+str(name)+'. Usa soltanto gli ID misurati forniti.')
        return self.regions[name]

    def point(self,x,y):
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in (x,y)):raise GeometryError('slide.point usa coordinate normalizzate da 0 a 1, mai pixel.')
        return [(x-.5)*self.slide_width,(.5-y)*self.slide_height,0]

    def bounds(self,name,padding=.006):
        if type(padding) not in (int,float) or not math.isfinite(padding) or not 0<=padding<=.04:raise GeometryError('Margine evidenziazione non valido: da 0 a 0,04.')
        r=self.region(name);l=max(0,r['left']-padding);t=max(0,r['top']-padding)
        right=min(1,r['left']+r['width']+padding);bottom=min(1,r['top']+r['height']+padding)
        return self.point((l+right)/2,(t+bottom)/2),(right-l)*self.slide_width,(bottom-t)*self.slide_height

    def center(self,name):return self.bounds(name,0)[0]
    def width(self,name):return self.bounds(name,0)[1]
    def height(self,name):return self.bounds(name,0)[2]

    def place(self,mobject,name):
        """Fit a free Manim object into a measured region without distortion."""
        point,w,h=self.bounds(name,0)
        mw,mh=float(mobject.width),float(mobject.height)
        if mw<=0 or mh<=0:raise GeometryError('Oggetto senza dimensioni: crea testo, immagine o gruppo prima di slide.place.')
        return mobject.scale(min(w/mw,h/mh)).move_to(point)

    def box(self,name,color='#FF8C42',padding=.006,**style):
        from manim import Rectangle
        point,w,h=self.bounds(name,padding)
        return Rectangle(width=w,height=h,color=color,**style).move_to(point)

    def ellipse(self,name,color='#FF8C42',padding=.006,**style):
        from manim import Ellipse
        point,w,h=self.bounds(name,padding)
        return Ellipse(width=w,height=h,color=color,**style).move_to(point)

    def underline(self,name,color='#FF8C42',padding=.003,**style):
        from manim import Line
        point,w,h=self.bounds(name,padding);x,y,_=point
        return Line([x-w/2,y-h/2,0],[x+w/2,y-h/2,0],color=color,**style)

    def pointer(self,name,color='#FF8C42',**style):
        from manim import Arrow
        point,w,h=self.bounds(name,0);x,y,_=point
        # Pick the side with most available space; both endpoints stay on slide.
        margins=[x-w/2+self.slide_width/2,self.slide_width/2-x-w/2,y-h/2+self.slide_height/2,self.slide_height/2-y-h/2]
        side=max(range(4),key=margins.__getitem__);distance=min(.8,max(.03,margins[side]*.7))
        if max(margins)<.03:return Arrow([x-.4,y,0],[x,y,0],buff=0,color=color,**style)
        end=[[x-w/2,y,0],[x+w/2,y,0],[x,y-h/2,0],[x,y+h/2,0]][side]
        start=list(end);axis=0 if side<2 else 1;start[axis]+=distance*(-1 if side in (0,2) else 1)
        return Arrow(start,end,buff=0,color=color,**style)


def check_layout(scene,width,height):
    """Check settled 2D presentation frames; never constrain normal/3D scenes."""
    # Moving/3D cameras project world positions differently. Their animation
    # remains free; checking world XY boxes would incorrectly reject valid code.
    if any(c.__name__ in ('ThreeDScene','MovingCameraScene') for c in type(scene).__mro__):return
    objects=[];texts=[];seen=set()
    def visible(obj):
        if hasattr(obj,'get_opacity'):
            try:return float(obj.get_opacity())>.01
            except (TypeError,ValueError,AttributeError):pass
        opacities=[]
        for method in ('get_fill_opacity','get_stroke_opacity'):
            if hasattr(obj,method):
                try:
                    value=getattr(obj,method)()
                    opacities.append(float(value.max() if hasattr(value,'max') else value))
                except (TypeError,ValueError,AttributeError):pass
        return not opacities or max(opacities)>.01
    def visit(obj,inside_text=False):
        if id(obj) in seen:return
        seen.add(id(obj));kind=type(obj).__name__
        text=kind in ('Text','MarkupText','Paragraph','Tex','MathTex')
        if text and not inside_text and visible(obj):texts.append(obj)
        children=getattr(obj,'submobjects',[])
        if not children and visible(obj) and (getattr(obj,'has_points',lambda:False)() or 'ImageMobject' in kind):objects.append(obj)
        for child in children:visit(child,inside_text or text)
    for obj in scene.mobjects:visit(obj)
    def box(obj):
        p=obj.get_center();w=float(obj.width);h=float(obj.height)
        return float(p[0])-w/2,float(p[1])-h/2,float(p[0])+w/2,float(p[1])+h/2
    problems=[];margin=.08
    for obj in objects:
        l,b,r,t=box(obj)
        if l<-width/2-margin or r>width/2+margin or b<-height/2-margin or t>height/2+margin:
            problems.append('elemento fuori inquadratura ('+type(obj).__name__+')')
            break
    for i,a in enumerate(texts):
        al,ab,ar,at=box(a);area=max(0,ar-al)*max(0,at-ab)
        for b in texts[i+1:]:
            bl,bb,br,bt=box(b);other=max(0,br-bl)*max(0,bt-bb)
            overlap=max(0,min(ar,br)-max(al,bl))*max(0,min(at,bt)-max(ab,bb))
            if min(area,other)>.0001 and overlap/min(area,other)>.35:
                problems.append('blocchi di testo sovrapposti');break
        if len(problems)>=2:break
    if problems:
        raise GeometryError('Impaginazione slide: '+', '.join(problems)+'. Correggi posizioni e dimensioni usando slide.place e gli ancoraggi misurati. Le coordinate Manim hanno origine al centro, x da -'+str(round(width/2,3))+' a +'+str(round(width/2,3))+', y da -'+str(round(height/2,3))+' a +'+str(round(height/2,3))+'. Non modificare solo la durata.')
