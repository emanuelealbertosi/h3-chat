import unittest
import threading
from unittest.mock import Mock

from h3chat.slide_html import validate,generate,InvalidPage


class SeparateStylesTests(unittest.TestCase):
    def test_separate_css_fence_is_retained_inside_document(self):
        raw='```html\n<html><head></head><body><main>Testo</main></body></html>\n```\n```css\nbody{background:#123;color:white}\n```'
        html=validate(raw)
        self.assertIn('<style>body{background:#123;color:white}</style>\n</head>',html)
        self.assertNotIn('```',html)

    def test_style_outside_fence_survives_but_explanation_does_not(self):
        raw='Ecco la pagina:\n```html\n<main>Contenuto</main>\n```\n<style>main{display:grid}</style>\nUna spiegazione.'
        self.assertEqual(validate(raw),'<style>main{display:grid}</style>\n<main>Contenuto</main>')

    def test_css_before_html_and_existing_embedded_style(self):
        raw='```css\nmain{color:red}\n```\n```html\n<style>body{margin:0}</style><main>Contenuto</main>\n```'
        html=validate(raw)
        self.assertEqual(html.count('body{margin:0}'),1)
        self.assertEqual(html.count('main{color:red}'),1)

    def test_empty_style_comments_and_script_do_not_count_as_formatting(self):
        for extra in ('','<style></style>','<style>/* body{color:red} */</style>','<script>let css="color:red";</script>'):
            with self.subTest(extra=extra),self.assertRaisesRegex(InvalidPage,'CSS'):
                validate(extra+'<main class="panel">Testo</main>',require_style=True)
        self.assertIn('color:red',validate('<main style="color:red">Testo</main>',require_style=True))

    def test_missing_style_gets_one_repair_and_uses_repaired_css(self):
        engine=Mock();engine.completion.side_effect=[('<main>Bozza</main>','stop'),('```html\n<main>Testo</main>\n```\n```css\nbody{color:white;background:#123}\n```','stop')]
        result=generate(engine,[{'role':'user','content':'Ricrea la slide'}],{},threading.Event(),lambda raw:None,lambda text:None,require_style=True)
        self.assertIn('<style>',result)
        self.assertEqual(engine.completion.call_count,2)
        self.assertIn('CSS',engine.completion.call_args.args[0][-1]['content'])


if __name__=='__main__':unittest.main()
