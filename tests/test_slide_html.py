import threading,unittest
from unittest.mock import Mock
from h3chat.slide_html import validate,generate,InvalidPage
from h3chat.downloads import Cancelled

class HtmlPageTests(unittest.TestCase):
 def test_styles_are_not_visible_html_even_when_they_contain_markup_strings(self):
  for raw in ('<style>.spark.s239', '<style>.spark{color:red}</style>', '<style>.x:after{content:"<div>"}</style>', '<script>"<main>"</script>', '<main>Contenuto</main><style>.broken{'):
   with self.assertRaises(InvalidPage):validate(raw)
  for raw in ('<main>Contenuto</main><style>main{color:red}</style>', '<figure><img data-asset-id="figure"></figure>', '<table><tr><td>Uno</td></tr></table>'):
   self.assertEqual(validate(raw),raw)

 def test_invalid_page_is_retried_once_without_changing_token_budget_or_request(self):
  engine=Mock();engine.completion.side_effect=[('<style>.spark.s239','stop'),('<section data-panel="1"><h1 data-motion="fade">SKY</h1></section><style>h1{color:cyan}</style>','stop')]
  request=[{'role':'user','content':'Neon 9:16, immagine autorizzata image, musica già composta.'}]
  settings={'max_tokens':40000,'temperature':.8,'think_level':'low'};stage=Mock()
  result=generate(engine,request,settings,threading.Event(),Mock(),stage,'Scena 1')
  self.assertIn('SKY',result);self.assertEqual(engine.completion.call_count,2);self.assertEqual(len(request),1)
  retry=engine.completion.call_args;self.assertEqual(retry.args[1]['max_tokens'],40000);self.assertEqual(retry.args[1]['think_level'],'off')
  self.assertEqual(retry.args[0][0],request[0]);self.assertIn('elementi HTML visibili',retry.args[0][-1]['content']);stage.assert_called_once()

 def test_repair_is_bounded_and_cancel_is_never_retried(self):
  engine=Mock();engine.completion.return_value=('<style>h1{}','stop')
  with self.assertRaisesRegex(ValueError,'dopo due tentativi'):
   generate(engine,[],{'max_tokens':40,'temperature':.7},threading.Event(),Mock(),Mock())
  self.assertEqual(engine.completion.call_count,2)
  engine.reset_mock();engine.completion.side_effect=Cancelled()
  with self.assertRaises(Cancelled):generate(engine,[],{},threading.Event(),Mock(),Mock())
  self.assertEqual(engine.completion.call_count,1)

 def test_truncated_or_oversized_page_can_be_replaced_by_a_complete_page(self):
  for first in ('length','oversized'):
   engine=Mock();calls=[]
   def completion(request,settings,cancel,on_text):
    calls.append(request)
    if len(calls)==1:
     if first=='oversized':on_text('<style>'+('x'*80001))
     return '<main>Parziale','length'
    on_text('<main>Completa</main>');return '<main>Completa</main>','stop'
   engine.completion.side_effect=completion
   self.assertEqual(generate(engine,[],{'max_tokens':40000,'temperature':.7},threading.Event(),Mock(),Mock()),'<main>Completa</main>')
   self.assertEqual(len(calls),2)
