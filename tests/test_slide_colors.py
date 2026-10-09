import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat.slide_colors import brief
from h3chat.slides import options, encode, edit_options, validate_content
from h3chat.slide_generation_images import plan_images


class SlideColorTests(unittest.TestCase):
    def test_automatic_defaults_preserve_existing_instructions(self):
        self.assertEqual(options(''), {'count':8,'format':'16:9','engine':'llm'})
        self.assertEqual(brief({}), '')
        self.assertEqual(brief({'background':'auto','palette':'auto','background_color':'#123456'}), '')

    def test_validated_preferences_and_custom_color(self):
        opts=options('', {'background':'custom','background_color':'#ABCDEF','palette':'pastel'})
        self.assertEqual(opts['background_color'], '#abcdef')
        self.assertIn('#abcdef', brief(opts))
        self.assertIn('colori pastello', brief(opts))
        self.assertEqual(options('', {'background':'custom'})['background_color'], '#f7f3e8')
        for invalid in ({'background':[]},{'palette':'dark'},{'palette':None},
                        {'background_color':'red'},{'background_color':'#fff'},
                        {'background_color':'#ffffff;display:none'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):options('', invalid)

    def test_deck_edit_preserves_colors_and_legacy_decks_still_validate(self):
        deck={'version':1,'engine':'llm','format':'4:3','pages':[{'title':'A','status':'ready','html':'<main><h1>A</h1></main>'}]}
        validate_content(encode(deck), [])
        deck.update(background='custom',background_color='#eaf0ff',palette='natural')
        validate_content(encode(deck), [])
        opts=edit_options('Aggiungi una slide', encode(deck))
        self.assertEqual(opts['count'], 2)
        for key in ('background','background_color','palette'):self.assertEqual(opts[key], deck[key])
        deck['background_color']='#invalid'
        with self.assertRaises(ValueError):validate_content(encode(deck), [])

    def test_background_is_independent_of_palette_and_infographic_settings(self):
        instruction=brief({'background':'light','palette':'neon','_infographic':{'palette':'dark'}})
        self.assertIn('Sfondo principale chiaro', instruction)
        self.assertIn('Neon non obbliga uno', instruction)
        self.assertIn('prompt corrente', instruction)
        self.assertEqual(brief({'_infographic':{'palette':'neon','frame':'dark'}}), '')

    def test_image_planner_receives_selected_slide_palette(self):
        engine=SimpleNamespace(completion=Mock(return_value=(json.dumps({'images':[
            {'slide':1,'prompt':'A visual example','description':'Esempio'}]}),'stop')))
        settings={'context':8000,'prompt_max_tokens':2200,
                  '_slides':{'engine':'llm','background':'custom','background_color':'#eaf0ff','palette':'pastel'}}
        result=plan_images(engine,{'title':'A','slides':[{'title':'A','purpose':'Explain'}]},[],settings,
                           {'architecture':'anima','name':'Fixture'},threading.Event(),lambda _:None)
        self.assertEqual(len(result),1)
        request=engine.completion.call_args.args[0][-1]['content']
        self.assertIn('#eaf0ff', request);self.assertIn('colori pastello', request)
        self.assertNotIn('PREFERENZE COLORE', brief({'palette':'auto'}))


if __name__=='__main__':unittest.main()
