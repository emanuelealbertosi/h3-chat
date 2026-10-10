import unittest
from h3chat.infographics import options,validate_motion
from h3chat.infographic_text import CHOICES,EFFECTS,brief
from h3chat.infographic_animation import playable
from h3chat.infographic_choreography import targets,apply_plan

class TextOptionsTests(unittest.TestCase):
    def test_legacy_options_keep_automatic_text_and_existing_values(self):
        result=options(value={'duration':120,'style':'playful','format':'16:9'})
        self.assertEqual(result['duration'],120)
        self.assertEqual(result['text_motion'],'auto')
        self.assertEqual(result['text_scope'],'headings')
        self.assertEqual(result['text_color'],'auto')

    def test_every_choice_survives_saved_timeline_validation(self):
        for key,values in CHOICES.items():
            for value in values:
                with self.subTest(key=key,value=value):
                    configured=options(value={key:value})
                    deck={'pages':[{}],'infographic':{'version':1,'durations':[10],
                        'transition':'cut','sfx':'none','options':configured}}
                    validate_motion(deck)
                    self.assertEqual(configured[key],value)

    def test_invalid_colors_and_options_are_rejected(self):
        for key,value in [('text_primary','red'),('text_accent','#fff'),('text_primary','url(file://private)'),
                          ('text_primary',False),('text_motion','script'),('text_speed',99),('text_scope','video')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):options(value={key:value})
        self.assertEqual(options(value={'text_accent':'#FF00aB'})['text_accent'],'#FF00aB')

    def test_llm_and_repair_accept_new_effects_without_rewriting_content(self):
        html='<h1>Novità è 👨‍👩‍👧!</h1>'
        for effect in ('bump','drop','wave','flip','typewriter'):
            result=apply_plan(html,targets(html),{'animations':[{'target':'e1','motion':effect,
                'start':.2,'duration':1,'out':-1,'ease':'smooth'}]},10)
            self.assertTrue(playable(result,10));self.assertIn('Novità è 👨‍👩‍👧!',result)
            self.assertIn(effect,EFFECTS)
        self.assertIn('data-text="key"',brief(options()))

if __name__=='__main__':unittest.main()
