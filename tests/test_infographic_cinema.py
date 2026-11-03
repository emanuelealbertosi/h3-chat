import unittest,threading
from unittest.mock import Mock,patch
from h3chat.infographics import options
from h3chat.infographic_cinema import brief,validate_layers,ensure

class CinemaTests(unittest.TestCase):
    def test_image_background_needs_no_redundant_svg_scenery_and_cannot_be_omitted(self):
        ident='a'*32
        html=f'<div data-depth=".35" data-layer-role="background-image"><img data-asset-id="{ident}"></div><div data-depth="0">Titolo</div>'
        validate_layers(html)
        planned=[{'id':ident,'description':'Foto di sfondo'}];engine=Mock()
        self.assertEqual(ensure(engine,[],{},threading.Event(),html,{'visual_mode':'sequence'},lambda _:None,lambda _:None,planned),html)
        engine.completion.assert_not_called()
        with patch('h3chat.slide_html.generate',return_value=html) as generate:
            self.assertEqual(ensure(engine,[],{},threading.Event(),'<div>SVG senza immagine</div>',{'visual_mode':'sequence'},lambda _:None,lambda _:None,planned),html)
            self.assertIn(ident,generate.call_args.args[1][-1]['content'])
        with patch('h3chat.slide_html.generate',return_value=html.replace(ident,'b'*32)),self.assertRaises(ValueError):
            ensure(engine,[],{},threading.Event(),'<div>SVG senza immagine</div>',{'visual_mode':'sequence'},lambda _:None,lambda _:None,planned)

    def test_three_modes_preserve_video_panels_and_saved_parameters(self):
        old={'layout':'grid3x2','video_background':'auto','video_id':'a'*32,'video_audio':'duck','video_start':'panel','panel_order':'654321','panel_appearance':'sequence','panel_interval':1.2,'background':'light','image_model':'model-selected','images':'auto'}
        for mode in ('normal','decorative','sequence'):
            config=options(value=old|{'visual_mode':mode})
            for key,value in old.items():self.assertEqual(config[key],value)
            self.assertEqual(config['visual_mode'],mode)
        self.assertEqual(options()['visual_mode'],'normal')
        self.assertEqual(brief(options()),'')
        self.assertIn('ILLUSTRATO',brief(options(value={'visual_mode':'decorative'})))
        self.assertEqual(options('Un piano sequenza',old)['visual_mode'],'sequence')

    def test_only_sequence_requires_three_real_depth_wrappers(self):
        engine=Mock();html='<main>Originale</main>'
        self.assertEqual(ensure(engine,[],{},threading.Event(),html,options(),lambda _:None,lambda _:None),html);engine.completion.assert_not_called()
        with self.assertRaises(ValueError):validate_layers(html)
        with self.assertRaises(ValueError):validate_layers('<div data-depth="NaN"></div>')
        with self.assertRaises(ValueError):validate_layers('<div data-depth=".35"><div data-depth="1"><div data-depth="1.65"></div></div></div>')
        fixed='<div data-depth=".35">Montagne</div><div data-depth="1">Edificio</div><div data-depth="1.65">Albero</div>'
        validate_layers(fixed)
        with patch('h3chat.slide_html.generate',return_value=fixed) as generate:
            self.assertEqual(ensure(engine,[],{},threading.Event(),html,options(value={'visual_mode':'sequence'}),lambda _:None,lambda _:None),fixed)
            generate.assert_called_once()
