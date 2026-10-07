import ast,unittest
from pathlib import Path
from native.slide_geometry import SlideSpace,GeometryError,anchors,validate_annotations,check_layout


class GeometryTests(unittest.TestCase):
    def test_reconstruction_placement_fits_union_without_distortion(self):
        class Object:
            width=8;height=2
            def scale(self,f):self.width*=f;self.height*=f;return self
            def move_to(self,p):self.position=p;return self
        regions=[{'id':'a','left':.1,'top':.2,'width':.5,'height':.1},
                 {'id':'b','left':.1,'top':.3,'width':.5,'height':.1}]
        s=SlideSpace(16,9,4/3,regions);obj=s.place(Object(),['a','b'])
        self.assertAlmostEqual(obj.width/obj.height,4)
        self.assertAlmostEqual(obj.width,6);self.assertAlmostEqual(obj.height,1.5)
        self.assertAlmostEqual(obj.position[0],-1.8);self.assertAlmostEqual(obj.position[1],1.8)
        with self.assertRaises(GeometryError):s.region([])

    def test_settled_2d_layout_reports_overflow_and_text_overlap_only(self):
        class Object:
            submobjects=[]
            def __init__(self,x=0,y=0,w=2,h=1,opacity=1):self.x=x;self.y=y;self.width=w;self.height=h;self.opacity=opacity
            def get_center(self):return self.x,self.y,0
            def has_points(self):return True
            def get_opacity(self):return self.opacity
        class Text(Object):pass
        class Scene:
            def __init__(self,*objs):self.mobjects=list(objs)
        check_layout(Scene(Object(),Text()),16,9) # Shape behind a label is legitimate.
        check_layout(Scene(Text(-3),Text(3),Object(100,opacity=0)),16,9)
        with self.assertRaisesRegex(GeometryError,'fuori inquadratura'):check_layout(Scene(Object(10)),16,9)
        with self.assertRaisesRegex(GeometryError,'sovrapposti'):check_layout(Scene(Text(),Text(.4)),16,9)
        class ThreeDScene(Scene):pass
        check_layout(ThreeDScene(Object(100)),16,9) # World coordinates are not screen projection.

    def test_normalized_bounds_follow_the_fitted_slide_with_letterboxing(self):
        region={'id':'target','left':.2,'top':.3,'width':.4,'height':.2}
        for frame,aspect in (((16,9),4/3),((4,3),16/9),((16,9),9/16),((16,10),16/10)):
            with self.subTest(frame=frame,aspect=aspect):
                s=SlideSpace(*frame,aspect,[region]);point,w,h=s.bounds('target',0)
                self.assertAlmostEqual(s.slide_width/s.slide_height,aspect)
                self.assertAlmostEqual(point[0],-.1*s.slide_width)
                self.assertAlmostEqual(point[1],.1*s.slide_height)
                self.assertAlmostEqual(w,.4*s.slide_width);self.assertAlmostEqual(h,.2*s.slide_height)
                self.assertEqual(s.point(0,0),[-s.slide_width/2,s.slide_height/2,0])
                self.assertEqual(s.point(1,1),[s.slide_width/2,-s.slide_height/2,0])

    def test_invalid_references_and_pixel_points_are_rejected(self):
        s=SlideSpace(16,9,16/9,anchors({}))
        for xy in ((864,486),(-.1,.5),(float('nan'),0)):
            with self.assertRaises(GeometryError):s.point(*xy)
        with self.assertRaises(GeometryError):s.bounds('invented')
        with self.assertRaises(GeometryError):s.bounds('slide',.8)
        for row in ({'left':.9,'top':0,'width':.2,'height':1},{'left':0,'top':0,'width':float('nan'),'height':1}):
            with self.assertRaises(GeometryError):SlideSpace(16,9,16/9,[row|{'id':'target'}])
        point,w,h=s.bounds('slide',.04)
        self.assertEqual(point,[0,0,0]);self.assertEqual((w,h),(16,9))

    def test_measured_anchors_are_not_limited_by_crop_assets(self):
        measured=[{'id':f'text-{i:03}','kind':'text','text':'Testo','left':.1,'top':.1,'width':.4,'height':.1} for i in range(20)]
        self.assertEqual(len(anchors({'anchors':measured,'regions':[]})),21)

    def test_pdf_fragments_with_different_glyph_heights_form_measured_lines(self):
        # Native worker has a stdout protocol; exercise its pure grouping function
        # without importing its process entrypoint into the unittest runner.
        tree=ast.parse((Path(__file__).resolve().parents[1]/'native/presentation-worker.py').read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='text_regions')
        namespace={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'text_regions','exec'),namespace)
        class Page:
            boxes=[(10,60,18,80),(19,60,27,73),(28,60,36,74),(37,68,39,80),
                   (40,60,48,80),(60,60,90,80),(10,40,14,48),(16,40,20,48),(22,40,26,48)]
            def count_rects(self):return len(self.boxes)
            def get_rect(self,index):return self.boxes[index]
            def get_text_bounded(self,left,bottom,right,top):return "Cos'è il BLSD?" if top>60 else 'N O R'
        regions=namespace['text_regions'](Page(),100,100)
        self.assertEqual(len(regions),2)
        self.assertEqual(regions[0]['text'],"Cos'è il BLSD?")
        for actual,expected in zip(regions[0]['box'],[.1,.2,.9,.4]):self.assertAlmostEqual(actual,expected)

    def test_legacy_pixel_shapes_camera_moves_and_anchor_moves_are_rejected(self):
        for body in ('r=Rectangle(width=864,height=486)',
                     'r=R(width=864,height=486)',
                     'r=slide.box("text-001").move_to([100,100,0])',
                     'r=slide.ellipse("image-001");r.animate.shift(RIGHT)',
                     'r=slide.box("text-001");other=r;other.scale(100)',
                     'self.camera.frame.shift(RIGHT)'):
            with self.subTest(body=body),self.assertRaises(GeometryError):
                validate_annotations('from manim import Rectangle as R\n'+body)
        validate_annotations('from manim import *\nclass Demo(Scene):\n def construct(self):\n  ring=slide.ellipse("image-001")\n  self.play(Create(ring))\n  self.play(ring.animate.set_stroke(opacity=.4))\n  self.play(Indicate(ring))')


if __name__=='__main__':unittest.main()
