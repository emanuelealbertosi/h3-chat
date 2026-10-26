import threading
import unittest
from unittest.mock import Mock
from h3chat.slide_content_guard import leaks,explicit_revision_page
from h3chat.slide_html import generate,validate


class ContentGuardTests(unittest.TestCase):
    def test_render_instructions_are_repaired_not_silently_published(self):
        bad='<main><h1>Porte logiche</h1><p>Non stampare <b>istruzioni grafiche</b>.</p></main><style>main{color:navy}</style>'
        good='<main><h1>Porte logiche</h1><p>AND restituisce vero quando entrambi gli ingressi sono veri.</p></main><style>main{color:navy}</style>'
        engine=Mock();engine.completion.side_effect=[(bad,'stop'),(good,'stop')]
        self.assertEqual(generate(engine,[],{'max_tokens':3000},threading.Event(),Mock(),Mock()),good)
        self.assertEqual(engine.completion.call_count,2)
        self.assertIn('istruzioni interne',engine.completion.call_args.args[0][-1]['content'])
        self.assertEqual(validate(bad),bad,'An older artifact remains readable so it can be repaired.')

    def test_technical_lessons_code_and_private_css_are_not_censored(self):
        self.assertFalse(leaks('<h1>HTML e CSS</h1><p>Viewport, layout, note e direzione artistica.</p>'))
        self.assertFalse(leaks('<style>/* RICHIESTA ATTUALE DELL’UTENTE */ h1{color:red}</style><h1>AND</h1>'))
        self.assertFalse(leaks('<h1>Prompt</h1><pre><code>Non stampare istruzioni grafiche.</code></pre>'))
        self.assertTrue(leaks('<p>SFONDO GESTITO DALL’APP: collection.</p>'))

    def test_only_an_unambiguous_explicit_human_page_binds_the_revision(self):
        for request in ('Modifica la seconda slide: sistema i colori.', 'Correggi slide 2.', 'Fix the second slide.'):
            self.assertEqual(explicit_revision_page(request),2)
        self.assertEqual(explicit_revision_page('Sistema il layout della slide 32.'),32)
        for request in ('Crea due slide sulla logica.', 'Modifica slide 1 e slide 2.', 'Modifica slide 2 e 3.', 'Correggi slide 2–4.', 'Modifica prima e seconda slide.', 'Rivedi la presentazione.'):
            self.assertIsNone(explicit_revision_page(request))
