import unittest,ast,math
from pathlib import Path
from types import SimpleNamespace
from h3chat.image_options import options,validate_overrides
from h3chat.store import DEFAULTS

class AspectTests(unittest.TestCase):
    def test_explicit_pixel_canvas_wins_over_settings_and_reference(self):
        model={'id':'moss','architecture':'moss','engine':'vision','width':1024,'height':1024}
        result=options(model,DEFAULTS|{'image_aspect':'4:3'},'Un faro, risoluzione 1024x576')
        self.assertEqual((result['width'],result['height']),(1024,576))
        self.assertFalse(result['preserve_reference_aspect'])
        self.assertEqual(result['aspect'],'16:9')
        wide=options(model,DEFAULTS,'risoluzione 1920x1080');self.assertEqual((wide['width'],wide['height']),(1920,1080))
        with self.assertRaises(ValueError):options(model,DEFAULTS,'risoluzione 5000x5000')
    def test_moss_keeps_megapixels_and_exact_requested_pixels(self):
        model={'id':'moss','architecture':'moss','engine':'vision','width':1024,'height':1024}
        square=options(model,DEFAULTS,'Un faro 1500*1500')
        self.assertEqual((square['width'],square['height'],square['megapixels']),(1500,1500,2.25))
        settings=DEFAULTS|{'image_overrides':{'moss':{'megapixels':2.25,'aspect':'16:9'}}}
        wide=options(model,settings)
        self.assertEqual((wide['width'],wide['height']),(2000,1125));self.assertGreaterEqual(wide['width']*wide['height'],2_250_000)
        overridden=options(model,settings,'Un faro, 1 MP, quadrato')
        self.assertEqual((overridden['width'],overridden['height']),(1000,1000))
        default=options(model,DEFAULTS,'un faro, 16:9')
        self.assertGreaterEqual(default['width']*default['height'],1024**2)
    def setUp(self):self.model={'id':'test','architecture':'qwen21','engine':'vision','width':1024,'height':1024}
    def test_setting_prompt_precedence_and_reference_behavior(self):
        automatic=options(self.model,DEFAULTS)
        self.assertTrue(automatic['preserve_reference_aspect'])
        settings=DEFAULTS|{'image_aspect':'4:3','image_overrides':{'test':{'aspect':'1:1'}}}
        square=options(self.model,settings);self.assertEqual(square['width'],square['height'])
        landscape=options(self.model,settings,'Un paesaggio in formato 16:9')
        self.assertEqual(landscape['width']*9,landscape['height']*16)
        self.assertFalse(landscape['preserve_reference_aspect'])
        vertical=options(self.model,settings,'Immagine verticale')
        self.assertEqual(vertical['width']*16,vertical['height']*9)
        self.assertTrue(all(256<=vertical[k]<=1536 and vertical[k]%64==0 for k in ('width','height')))
    def test_invalid_settings_rejected(self):
        with self.assertRaises(ValueError):validate_overrides({'test':{'aspect':'7:99'}})

    def test_all_image_families_honor_saved_format_and_literal_prompt_override(self):
        for arch in ('qwen21','qwen-edit','anima','krea2','flux2','sd15','moss'):
            model={'id':arch,'architecture':arch,'engine':'vision','width':1024,'height':1024}
            settings=DEFAULTS|{'image_overrides':{arch:{'aspect':'4:3','seed':42}}}
            with self.subTest(architecture=arch):
                saved=options(model,settings)
                self.assertEqual(saved['aspect'],'4:3')
                self.assertGreater(saved['width'],saved['height'])
                for prompt,aspect in (('Un faro, 16:9','16:9'),('Un faro, 9:16','9:16'),('Un faro quadrato','1:1')):
                    result=options(model,settings,prompt)
                    self.assertEqual(result['aspect'],aspect)
                    self.assertFalse(result['preserve_reference_aspect'])
                    self.assertEqual(result['seed'],42)

    def test_native_edit_output_uses_chosen_canvas_instead_of_reference_shape(self):
        class Tensor:
            def __init__(self,shape):self.shape=shape
            def movedim(self,source,target):
                axes=list(self.shape);value=axes.pop(source);axes.insert(target if target>=0 else len(axes)+target+1,value);return Tensor(axes)
            def __getitem__(self,key):return self
        root=Path(__file__).resolve().parents[1];tree=ast.parse((root/'native/vision-worker.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker');cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('encode','references')]
        namespace={'math':math};exec(compile(ast.Module(body=[cls],type_ignores=[]),'<worker>','exec'),namespace)
        for architecture,scale in (('ming',8),('qwen21',16)):
            worker=namespace['Worker']();worker.architecture=architecture
            worker.torch=SimpleNamespace(zeros=lambda shape,**kw:Tensor(shape),zeros_like=lambda x:'zero')
            worker.comfy=SimpleNamespace(utils=SimpleNamespace(common_upscale=lambda x,w,h,*args:Tensor([1,3,h,w])),model_management=SimpleNamespace(intermediate_device=lambda:None))
            worker.vae=SimpleNamespace(encode=lambda x:x)
            clip=SimpleNamespace(tokenize=lambda text,**kw:text,encode_from_tokens_scheduled=lambda tokens:[['embedding',{}]])
            request={'prompt':'A scene','width':1024,'height':576,'cfg':1,'preserve_reference_aspect':False}
            _,_,latent=worker.encode(clip,request,[Tensor([1,480,640,3])])
            self.assertEqual(latent.shape[-2:],[576//scale,1024//scale])
        worker.architecture='moss';request.update(width=1500,height=1500)
        _,_,latent=worker.encode(clip,request,[])
        self.assertEqual(latent.shape[-2:],[94,94])

if __name__=='__main__':unittest.main()
