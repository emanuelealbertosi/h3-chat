import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from h3chat.video_engine import VideoEngine
from h3chat.video_options import DEFAULTS, resolve_canvas


class VideoAspectTests(unittest.TestCase):
    def resolve(self, images, sizes, prompt=''):
        return resolve_canvas(DEFAULTS, {'images':images},sizes,prompt)

    def test_start_frame_overrides_preset_and_prompt_without_stretching(self):
        value=self.resolve([{'index':1,'role':'keyframe','seconds':0}],[(1024,768)],'Anima in 16:9')
        self.assertEqual((value['aspect'],value['aspect_source'],value['format_image']),('4:3','image',1))
        self.assertEqual(value['output_width']*3,value['output_height']*4)
        self.assertEqual(value['width']%32,0);self.assertEqual(value['height']%32,0)
        self.assertLessEqual(value['output_width'],value['width'])
        self.assertLess(value['height']-value['output_height'],32)

    def test_first_keyframe_owns_format_even_after_identity_reference(self):
        plan=[{'index':1,'role':'reference','seconds':0},{'index':2,'role':'keyframe','seconds':5}]
        value=self.resolve(plan,[(1000,1000),(768,1024)],'in orizzontale')
        self.assertEqual(value['aspect'],'3:4');self.assertEqual(value['format_image'],2)

    def test_only_references_allow_explicit_prompt_format(self):
        images=[{'index':1,'role':'reference','seconds':0}]
        for prompt,ratio in [('Usa solo reference e crea il video 16:9','16:9'),('in formato verticale','9:16'),('reference in formato quadrato','1:1'),('non 16:9, voglio 4:3','4:3')]:
            with self.subTest(prompt=prompt):
                value=self.resolve(images,[(1024,768)],prompt)
                self.assertEqual(value['aspect'],ratio);self.assertEqual(value['aspect_source'],'prompt')
        self.assertEqual(self.resolve(images,[(1024,768)])['aspect'],'4:3')

    def test_portrait_source_and_custom_ratio_are_not_replaced_with_presets(self):
        value=self.resolve([{'index':1,'role':'keyframe','seconds':0}],[(600,1000)])
        self.assertEqual(value['aspect'],'3:5')
        self.assertEqual(value['output_width']*5,value['output_height']*3)
        self.assertEqual(value['output_width']%2,0);self.assertEqual(value['output_height']%2,0)
        self.assertEqual(self.resolve([],[],'video 2.35:1')['aspect'],'47:20')

    def test_text_only_uses_prompt_then_preset(self):
        self.assertEqual(self.resolve([],[])['aspect_source'],'preset')
        self.assertEqual(self.resolve([],[],'video 9:16')['aspect_source'],'prompt')

    def test_storyboard_song_timestamps_never_change_the_output_format(self):
        prompt='''SEGMENT 1 — 00:00–00:15
00:06–00:09 INSTRUMENTAL
SEGMENT 5 — 01:00–01:15
01:06–01:12 CHORUS
SEGMENT 6 — 01:15–01:29.544
01:24–01:29.544 FINALE'''
        value=self.resolve([],[],prompt)
        self.assertEqual((value['aspect'],value['aspect_source']),('16:9','preset'))
        self.assertEqual(value['output_width']*9,value['output_height']*16)
        self.assertEqual(self.resolve([],[],'Formato 9:16\n'+prompt)['aspect'],'9:16')
        self.assertEqual(self.resolve([{'index':1,'role':'keyframe','seconds':0}],[(1024,768)],prompt)['aspect'],'4:3')

    def test_clock_formats_and_ranges_are_ignored_but_real_ratios_work(self):
        for prompt in ('Parte a 01:06', 'Finish at 01:29.544', 'Scene 1:6–1:9',
                       'Scene 1:6 to 1:9', 'Da 1:6 a 1:9', 'Time 1:16:09',
                       'Start 01:06, end 01:15', 'Scene 0:12-0:15'):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.resolve([],[],prompt)['aspect'],'16:9')
        for prompt,ratio in [('Formato 1:6','1:6'),('Formato 0.5:1','1:2'),('Video 2.35:1','47:20'),('video 16:9','16:9'),('non 16:9, voglio 4:3','4:3')]:
            self.assertEqual(self.resolve([],[],prompt)['aspect'],ratio)

    def test_engine_saves_actual_format_before_model_load_including_exif_i2v(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);engine=VideoEngine();engine.root=engine.data=data
            image=data/'frame.jpg';exif=Image.Exif();exif[274]=6
            Image.new('RGB',(400,300)).save(image,exif=exif)
            session=Mock();session.uses=0;session.wait.return_value={}
            session.send.side_effect=lambda req:Path(req['output']).write_bytes(b'\0\0\0\x18ftypmp42')
            engine.tool_call=Mock(return_value={'sizes':[[300,400]]})
            for ident,refs,pictures,prompt,ratio in (
                ('text',[],[],'SEGMENT 5 — 01:00–01:15\n01:06–01:12 CHORUS','16:9'),
                ('image',[{'mime':'image/jpeg','path':'frame.jpg'}],[{'index':1,'role':'keyframe','seconds':0}],'Anima in 16:9','3:4')):
                def before_load(*args,**kwargs):
                    saved=json.loads((data/'outputs'/ident/'video-plan.json').read_text())['parameters']
                    self.assertEqual(saved['aspect'],ratio)
                    a,b=map(int,ratio.split(':'));self.assertEqual(saved['output_width']*b,saved['output_height']*a)
                    return session
                engine.start_video=Mock(side_effect=before_load)
                with patch('h3chat.veda.preflight'):
                    engine.generate_video({'id':'model','name':'Synthetic'}, {},{'prompt':prompt,'images':pictures,'audios':[]},refs,ident,threading.Event(),Mock(),prompt=prompt)
            engine.tool_call.assert_called_once()
            self.assertEqual(engine.tool_call.call_args.args[:2],('image-size-worker.py',{'paths':[str(image)]}))


if __name__=='__main__':unittest.main()
