import unittest
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


if __name__=='__main__':unittest.main()
