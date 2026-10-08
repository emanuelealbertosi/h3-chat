import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat.infographics import options,build,validate_motion
from h3chat.infographic_screen import LAYOUTS,brief,valid_panels,ensure_panels
from h3chat.infographic_video import select_many
from h3chat.service import Service
from h3chat.store import DEFAULTS
ROOT=Path(__file__).resolve().parents[1]

class ScreenTests(unittest.TestCase):
 def test_video_start_defaults_and_prompt_interval(self):
  self.assertEqual(options()['video_start'],'together')
  for prompt in ('Fai partire un video ogni 3 secondi','Usa un delay di 3 secondi fra i video','Video con intervallo di 3 secondi'):
   value=options(prompt,{'layout':'columns3'})
   self.assertEqual((value['video_start'],value['panel_appearance'],value['panel_interval'],value['duration']),('panel','sequence',3,30))
  value=options('Crea 21 secondi: fai partire un video ogni 3 secondi',{'layout':'columns3'})
  self.assertEqual(value['duration'],21)
  self.assertEqual(options('Video con un ritardo di 2,5 secondi',{'layout':'rows2'})['panel_interval'],2.5)
  self.assertEqual(options('Video di 21 secondi con delay di 3 secondi',{'layout':'columns3'})['duration'],21)
  self.assertEqual(options('Una lezione con esempi ogni 10 secondi',{'layout':'rows3'})['panel_interval'],.8)
  self.assertEqual(options(value={'panel_interval':30})['panel_interval'],30)
  for value in ({'video_start':'invalid'},{'panel_interval':31}):
   with self.assertRaises(ValueError):options(value=value)
 def test_static_scene_requires_llm_animation_repair_and_rejects_unusable_timing(self):
  from h3chat.infographic_animation import ensure,playable
  for html in ('<h1>Fermo</h1>','<h1 data-motion="appear">Fermo</h1>','<h1 data-motion="fade" data-start="nan">Errato</h1>','<h1 data-motion="fade" data-start="50">Fuori scena</h1>','<h1 data-motion="fade" data-duration="0">Errato</h1>'):
   self.assertFalse(playable(html,3))
  html='<h1 data-motion="typewriter" data-start=".3" data-duration="1">Testo</h1>';engine=Mock();engine.completion.return_value=(html,'stop')
  self.assertEqual(ensure(engine,[],{},threading.Event(),'<h1>Testo</h1>',3,lambda _:None),html)
  self.assertIn('La scena restituita è statica',engine.completion.call_args.args[0][-1]['content'])
  engine.completion.return_value=('<h1>Ancora fermo</h1>','stop')
  with self.assertRaises(ValueError):ensure(engine,[],{},threading.Event(),'<h1>Testo</h1>',3,lambda _:None)
 def test_defaults_and_all_orders(self):
  self.assertEqual(options()['layout'],'full')
  for order in ('123','132','213','231','312','321'):
   opts=options(value={'layout':'columns3','panel_appearance':'sequence','panel_order':order})
   self.assertIn('Ingressi in ordine '+order,brief(opts))
  for value in ({'layout':'columns4'},{'layout':'rows2','panel_order':'231'},{'panel_interval':True},{'panel_interval':float('nan')},{'panel_interval':0},{'panel_appearance':'other'}):
   with self.assertRaises(ValueError):options(value=value)
 def test_four_and_six_panel_orders_and_html_structure(self):
  for layout,count,order in (('grid2x2',4,'2413'),('grid3x2',6,'362514'),('grid2x3',6,'654321')):
   opts=options(value={'layout':layout,'panel_appearance':'sequence','panel_order':order})
   html=''.join(f'<section data-panel="{n}"><h1>{n}</h1></section>' for n in range(1,count+1))
   self.assertTrue(valid_panels(html,opts));self.assertIn(f'data-panel="{count}"',brief(opts));self.assertIn('Ingressi in ordine '+order,brief(opts))
   self.assertFalse(valid_panels(html.replace(f'data-panel="{count}"','data-panel="1"'),opts))
   for wrong in ('123',order+'1',order[:-1]+order[0],None,123456):
    with self.assertRaises(ValueError):options(value={'layout':layout,'panel_order':wrong})
 def test_panels_must_exist_once_as_siblings(self):
  opts=options(value={'layout':'columns3'})
  for html in ('<main><section data-panel="1"></section><section data-panel="2"></section><section data-panel="3"></section></main>', '<section data-panel="3"></section><section data-panel="1"></section><section data-panel="2"></section>'):
   self.assertTrue(valid_panels(html,opts))
  for html in ('<section data-panel="1"><section data-panel="2"></section></section><section data-panel="3"></section>', '<section data-panel="1"></section>', '<section data-panel="1"></section><section data-panel="2"></section><section data-panel="2"></section>'):
   self.assertFalse(valid_panels(html,opts))
 def test_global_overlay_is_allowed_in_split_prompt_and_structure(self):
  opts=options(value={'layout':'columns3'})
  html='<main>'+''.join(f'<section data-panel="{i}"></section>' for i in range(1,4))+'<div data-overlay="global" data-motion="zoom" data-start="15">POWER</div></main>'
  self.assertTrue(valid_panels(html,opts));self.assertIn('data-overlay="global"',brief(opts));self.assertNotIn('Nessun altro contenuto fuori dalle sezioni',brief(opts))
  self.assertIn('sfondo trasparente',brief(opts));self.assertIn('Solo se l’utente chiede esplicitamente',brief(opts))
 def test_malformed_model_structure_is_repaired_without_templates(self):
  opts=options(value={'layout':'rows2','panel_order':'21','panel_appearance':'sequence'});engine=Mock()
  html='<section data-panel="1"><h1>Originale</h1></section><section data-panel="2"><svg></svg></section>';engine.completion.return_value=(html,'stop')
  self.assertEqual(ensure_panels(engine,[],{},threading.Event(),'<h1>Originale</h1>',opts,lambda _:None),html)
  self.assertIn('Ingressi in ordine 21',engine.completion.call_args.args[0][-1]['content'])
  engine.completion.return_value=('<h1>Ancora incompleto</h1>','stop')
  with self.assertRaises(ValueError):ensure_panels(engine,[],{},threading.Event(),'<h1>Originale</h1>',opts,lambda _:None)
 def test_multiple_clips_are_authorized_and_bounded(self):
  clips=[{'id':str(i),'mime':'video/mp4'} for i in range(3)]
  self.assertEqual(select_many(options(value={'layout':'columns3','video_id':'2'}),clips),[clips[2],clips[0],clips[1]])
  with self.assertRaises(ValueError):select_many(options(),clips)
  six=clips+[{'id':str(i),'mime':'video/mp4'} for i in range(3,6)]
  self.assertEqual(select_many(options(value={'layout':'grid3x2'}),six),six)
  with self.assertRaises(ValueError):select_many(options(value={'layout':'grid3x2'}),six+[{'id':'extra','mime':'video/mp4'}])
  self.assertEqual(select_many(options(value={'layout':'columns3','video_background':'off'}),clips),[])
 def test_invalid_video_lists_are_validation_errors(self):
  for value in (None,[],[None],[{'asset_id':{}}]):
   with self.assertRaises(ValueError):validate_motion({'pages':[{}],'infographic':{'version':1,'durations':[5],'transition':'cut','sfx':'none','videos':value}})
 def test_pipeline_passes_layout_and_order_to_llm_and_keeps_three_sources(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as tmp:
   app=Service(ROOT,tmp,start_worker=False)
   try:
    chat=app.store.create_chat();folder=Path(tmp)/'uploads';folder.mkdir(exist_ok=True)
    clips=[]
    for i in range(3):
     (folder/f'v{i}.mp4').write_bytes(b'fixture');clips.append({'id':str(i)*32,'name':f'Video {i+1}.mp4','mime':'video/mp4','path':f'uploads/v{i}.mp4'})
    opts=options(value={'layout':'columns3','panel_appearance':'sequence','panel_order':'231','scenes':1,'voice':False,'output':'static','images':'provided'})
    settings=DEFAULTS|{'_infographic':opts,'_lab':'infographic'};ident=app.store.enqueue(chat['id'],'Componi tre video in sequenza',clips,settings,True,[])
    job=app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));payload=json.loads(job['payload']);history=app.store.messages(chat['id'],payload['until'])
    plan={'title':'Tre riquadri','visual_direction':'Neon, grafica libera','delivery':'warm','music_style':'','jingle_lyrics':'','scenes':[{'title':'Tre','purpose':'Confronto','narration':'Tre video.'}]}
    html=''.join(f'<section data-panel="{i+1}"><div data-video-asset-id="{clip["id"]}" style="height:100%"></div></section>' for i,clip in enumerate(clips))
    def completion(messages,s,cancel,on_text=None,schema=None):
     if schema:return json.dumps(plan),'stop'
     self.assertIn('Ingressi in ordine 231',messages[-1]['content']);self.assertIn(clips[2]['id'],messages[-1]['content']);on_text(html);return html,'stop'
    def probe(worker,request,*args,**kw):
     self.assertEqual(worker,'infographic-video-worker.py');Image.new('RGB',(20,20),'red').save(Path(tmp)/request['poster']);return {'duration':2,'width':320,'height':240,'audio':False}
    with patch.object(app.engine,'start_llama'),patch.object(app.engine,'completion',side_effect=completion),patch.object(app.engine,'chat_messages',return_value=[]),patch.object(app.engine,'tool_call',side_effect=probe):
     artifact=build(app,job,payload,history,settings,{},threading.Event(),lambda _:None,Path(tmp)/'log',{})
    deck=json.loads(artifact['content'][13:-4]);self.assertEqual(deck['pages'][0]['html'],html);self.assertEqual(len(deck['infographic']['videos']),3);self.assertNotIn('video',deck['infographic'])
    from h3chat.infographic_document import document
    doc=document(ROOT,tmp,deck,artifact['media']);self.assertEqual(doc.count('data-h3-video='),3);self.assertIn('data-panel=',doc)
   finally:app.close()
