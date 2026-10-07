import copy,json,tempfile,threading,unittest,wave
from pathlib import Path
from unittest.mock import patch
from h3chat.downloads import Cancelled
from h3chat.narrated_manim import requested,validate_plan,measured_scenes,checkpoint,scene_count,complete_json
from h3chat.service import Service
from h3chat.store import DEFAULTS

ROOT=Path(__file__).resolve().parents[1]
PLAN={'title':'Circuito','style':'Sfondo scuro, nodi verdi, frecce gialle.','scenes':[
    {'narration':'La batteria alimenta il circuito.','visual':'Disegna batteria e filo, anima il flusso.'},
    {'narration':'La lampada si accende.','visual':'Illumina la lampada mentre viene nominata.'}]}
CODE='from manim import *\nclass Demo(ThreeDScene):\n def construct(self):\n  self.add(Sphere()); self.wait(2)\n'
SOURCE={'title':'Circuito','code':CODE,'scene_name':'Demo'}
VOICE={'duration':7,'sample_rate':24000,'timeline':[
    {'scene_id':0,'text':PLAN['scenes'][0]['narration'],'start':0,'end':2},
    {'scene_id':1,'text':PLAN['scenes'][1]['narration'],'start':2.25,'end':7}]}

class ContractTests(unittest.TestCase):
    def test_only_empty_or_invalid_json_is_retried_and_tokens_are_not_silently_increased(self):
        from h3chat.remote_llm import StructuredCompletionError
        from h3chat.manim_code import SCHEMA
        from unittest.mock import Mock
        engine=Mock();engine.completion.side_effect=[StructuredCompletionError('bad'),(json.dumps(SOURCE),'stop')]
        tuning=DEFAULTS|{'max_tokens':2222}
        result=complete_json(engine,[],tuning,threading.Event(),lambda _:None,SCHEMA,'test')
        self.assertEqual(result,SOURCE);self.assertEqual(engine.completion.call_count,2)
        self.assertEqual(engine.completion.call_args.args[1]['max_tokens'],2222)
        for error in (RuntimeError('Credito API'),Cancelled()):
            engine.reset_mock();engine.completion.side_effect=error
            with self.assertRaises(type(error)):complete_json(engine,[],tuning,threading.Event(),lambda _:None,SCHEMA,'test')
            self.assertEqual(engine.completion.call_count,1)
        engine.completion.side_effect=[('','length')]
        with self.assertRaisesRegex(ValueError,'limite di output'):complete_json(engine,[],tuning,threading.Event(),lambda _:None,SCHEMA,'test')
    def test_explicit_and_prompt_routing_without_hijacking_other_tools(self):
        self.assertTrue(requested('Spiega il circuito',DEFAULTS|{'_voice':True,'_lab':'manim'}))
        for prompt in ('Crea un diagramma Manim con voce narrante','Genera Manim con voice-over','Spiega con Manim e narrazione'):
            self.assertTrue(requested(prompt,DEFAULTS))
        for prompt in ('Come crea Manim una narrazione?','Crea Manim senza voce','Crea Manim con audio allegato','Leggi questo testo'):
            self.assertFalse(requested(prompt,DEFAULTS))
        self.assertFalse(requested('Crea Manim con voce',DEFAULTS|{'_video':True}))
        self.assertFalse(requested('Crea Manim con voce',DEFAULTS|{'voice_auto':False}))
        self.assertFalse(requested('Crea Manim con voce',DEFAULTS|{'_lab':'slides'}))
    def test_measurements_use_samples_not_estimated_reading_time_and_include_pause(self):
        scene=measured_scenes(VOICE,PLAN)
        self.assertEqual([s['duration'] for s in scene],[2.25,4.75]);self.assertEqual(scene[1]['cues'][0]['end'],4.75)
        invalid=copy.deepcopy(VOICE);invalid['timeline'][1]['scene_id']=0
        with self.assertRaises(ValueError):measured_scenes(invalid,PLAN)
        invalid=copy.deepcopy(VOICE);invalid['timeline'][1]['start']=1
        with self.assertRaises(ValueError):measured_scenes(invalid,PLAN)
        invalid=copy.deepcopy(VOICE);invalid['duration']=601
        with self.assertRaises(ValueError):measured_scenes(invalid,PLAN)
        with self.assertRaises(ValueError):validate_plan(PLAN|{'scenes':[{'narration':'','visual':'a'}]})
        self.assertEqual(scene_count('Due scene 3D di 12 secondi'),2)
        with self.assertRaises(ValueError):scene_count('25 scene')

class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Service(ROOT,self.tmp.name,start_worker=False)
        self.model={'id':'fixture','name':'Fixture','capabilities':['chat'],'files':[],'vision':{'enabled':False}}
        self.renders=[];self.fail_second=False
        self.completions=[]
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def create(self,**body):
        chat=self.app.store.create_chat();self.chat_id=chat['id']
        with patch.object(self.app.engine,'require_model',return_value=self.model):result=self.app.send(chat['id'],{'prompt':'Crea Manim con voce sul circuito per 7 secondi','voice':True,'lab':'manim','canvas':True,'rag':False}|body)
        return self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],))
    def speech(self,app,folder,parts,settings,prompt,cancel,stage,log,meta):
        folder.mkdir(parents=True,exist_ok=True)
        with wave.open(str(folder/'voce.wav'),'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(bytes(7*24000*2))
        (folder/'testo-voce.txt').write_text('\n'.join(p['text'] for p in parts));(folder/'voce.srt').write_text('Synthetic captions')
        meta.update(voice_duration=7,voice_controls={'gender':'female'})
        return VOICE,[{'id':str(i),'name':name,'mime':mime,'path':(folder/name).relative_to(app.data).as_posix()} for i,(name,mime) in enumerate([('voce.wav','audio/wav'),('testo-voce.txt','text/plain'),('voce.srt','application/x-subrip')])]
    def complete(self,messages,settings,*args,**kw):
        self.completions.append(messages)
        value=PLAN if kw['schema'].get('properties',{}).get('scenes') else SOURCE
        return json.dumps(value),'stop'
    def render(self,worker,request,*args,**kwargs):
        self.assertEqual(worker,'manim-worker.py');self.renders.append(request)
        if self.fail_second and len(self.renders)==2:raise Cancelled()
        path=Path(request['output'])/'animation.mp4';path.write_bytes(b'\0\0\0\x18ftypisom')
        return {'path':str(path),'duration':2}
    def mux(self,engine,clips,audio,output,*args,**kwargs):
        self.assertEqual(kwargs['durations'],[2.25,4.75]);self.assertEqual(len(clips),2)
        self.assertTrue(Path(audio).is_file());output.write_bytes(b'\0\0\0\x18ftypisom')
        return {'path':str(output),'duration':7,'synchronization':'per-scene'}
    def execute(self,job,no_speech=False):
        with patch.object(self.app.engine,'require_model',return_value=self.model),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=self.complete),patch.object(self.app.engine,'tool_call',side_effect=self.render),patch('h3chat.narrated_manim.configuration'),patch('h3chat.narrated_manim.status',return_value={'lab':{'ready':True},'latex':{'ready':True}}),patch('h3chat.narrated_manim.synthesize',side_effect=AssertionError('Voice must be reused') if no_speech else self.speech),patch('h3chat.soundtrack.compose',side_effect=self.mux):
            self.app.execute_job(job,threading.Event())
        return self.app.store.messages(job['chat_id'])[-1]
    def test_one_request_creates_voice_full_python_timed_video_and_canvas_files(self):
        job=self.create();answer=self.execute(job)
        self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(answer['media'],[]);meta=answer['meta'];self.assertTrue(meta['narrated_manim'])
        self.assertEqual(meta['manim_voice_scenes'],2);self.assertEqual(meta['audio_composition']['synchronization'],'per-scene')
        media=meta['artifact']['media'];self.assertEqual(sum(m['mime']=='text/x-python' for m in media),2)
        self.assertTrue(any(m['mime']=='video/mp4' for m in media));self.assertTrue(any(m['mime']=='audio/wav' for m in media))
        self.assertIn('Measured voice cues',self.completions[1][-1]['content'])
        self.assertEqual([r['options']['duration'] for r in self.renders],[2.25,4.75])
    def test_failure_resume_keeps_voice_and_completed_clips_but_done_regenerates_fresh(self):
        job=self.create();self.fail_second=True;answer=self.execute(job)
        self.assertEqual(answer['status'],'cancelled');saved=checkpoint(self.app.data,job['id']);self.assertEqual(len(saved['completed']),1)
        ident=self.app.store.regenerate(job['chat_id']);new=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        self.assertEqual(json.loads(new['payload'])['settings']['_manim_voice_resume'],job['id'])
        self.fail_second=False;self.renders=[];self.completions=[];answer=self.execute(new,no_speech=True)
        self.assertEqual(answer['status'],'done',answer['meta'].get('error'));self.assertEqual(len(self.renders),1)
        self.assertEqual(len(self.completions),1);self.assertEqual(answer['meta']['manim_voice_recovered'],1)
        next_id=self.app.store.regenerate(job['chat_id']);fresh=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(next_id,))['payload'])
        self.assertNotIn('_manim_voice_resume',fresh['settings'])
        file=self.app.data/saved['voice']['media'][0]['path'];file.write_bytes(b'changed')
        with self.assertRaises(ValueError):checkpoint(self.app.data,job['id'])
    def test_rag_sources_reach_both_shared_script_and_free_python_generation(self):
        job=self.create(rag=True);payload=json.loads(job['payload']);payload['project_id']='synthetic-project'
        self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),job['id']));job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(job['id'],))
        fact='La batteria della fonte ha una tensione di 12 volt.'
        row={'id':1,'source_id':'s','name':'Circuito.pdf','location':'pagina 2','page':2,'text':fact,'source_url':''}
        with patch.object(self.app.knowledge,'project',return_value={'instructions':'Usa i dati del documento','sources_only':True}),patch.object(self.app.knowledge,'retrieve',return_value=([row],'lexical')):answer=self.execute(job)
        self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(answer['meta']['rag_sources'][0]['text'],fact)
        for messages in self.completions:
            self.assertIn(fact,messages[-1]['content']);self.assertIn('[R1]',messages[-1]['content'])
            self.assertIn('Rispondi solo usando le fonti RAG',messages[0]['content'])
    def test_visual_rag_content_parts_stay_valid_in_plan_and_each_scene(self):
        import sys
        sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
        from PIL import Image
        self.model['vision']={'enabled':True,'max_refs':4}
        self.app.catalog['fixture']=self.model
        path=self.app.data/'uploads'/'fixture-rag.png';path.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(100,100),'blue').save(path)
        job=self.create(rag=True);payload=json.loads(job['payload']);payload['project_id']='synthetic-project';payload['settings'].update(chat_model='fixture',vision_enabled=True)
        self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),job['id']));job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(job['id'],))
        self.model['vision']={'enabled':True,'max_refs':4}
        self.app.catalog['fixture']=self.model
        row={'id':1,'source_id':'s','name':'Circuito.pdf','location':'pagina 2','page':2,'text':'La batteria ha 12 volt.','source_url':'','image_path':'uploads/fixture-rag.png'}
        with patch.object(self.app.knowledge,'project',return_value={'instructions':'Usa il documento','sources_only':True}),patch.object(self.app.knowledge,'retrieve',return_value=([row],'lexical')):answer=self.execute(job)
        self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(len(self.completions),3)
        for messages in self.completions:
            parts=messages[-1]['content'];self.assertIsInstance(parts,list)
            self.assertTrue(all(isinstance(p,dict) and p.get('type') in ('text','image_url') for p in parts))
            self.assertTrue(any(p['type']=='image_url' for p in parts))
            text=''.join(p['text'] for p in parts if p['type']=='text');self.assertIn('12 volt',text);self.assertIn('[R1]',text)
        self.assertIn('Approximate desired speaking time',self.completions[0][-1]['content'][-1]['text'])
        self.assertIn('Previous visual scene',self.completions[-1][-1]['content'][-1]['text'])

    def test_previous_large_slide_gallery_does_not_block_plan_voice_or_scene_generation(self):
        self.model['vision']={'enabled':True,'max_refs':4}
        self.app.catalog['fixture']=self.model
        job=self.create();original_messages=self.app.store.messages
        images=[{'id':str(i),'name':f'Figura {i}','mime':'image/png','path':f'unselected-{i}.png'} for i in range(12)]
        previous={'role':'assistant','seq':0,'status':'done','content':'La batteria ha 12 volt. [R1]',
                  'media':images,'meta':{'artifact':{'content':'Presentazione con dodici immagini','media':images}}}
        def history(chat_id,until=None):
            values=original_messages(chat_id,until)
            return [copy.deepcopy(previous),*values] if until is not None else values
        with patch.object(self.app.store,'messages',side_effect=history):answer=self.execute(job)
        self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(len(self.completions),3);self.assertEqual(len(self.renders),2)
        for messages in self.completions:
            self.assertTrue(any('12 volt' in m['content'] for m in messages if isinstance(m['content'],str)))
            self.assertFalse(any(p.get('type')=='image_url' for m in messages if isinstance(m['content'],list) for p in m['content']))
        self.assertTrue(any(m['mime']=='audio/wav' for m in answer['meta']['artifact']['media']))

    def test_verbatim_assistant_off_does_not_rewrite_narration(self):
        from h3chat.narrated_manim import _plan
        exact='La batteria alimenta il circuito.'
        with patch.object(self.app.engine,'start_llama',side_effect=AssertionError('No rewriting')):
            plan=_plan(self.app,{'prompt':'Manim con voce. Testo: '+exact},[],DEFAULTS|{'_assistant':False},{},threading.Event(),lambda _:None,Path(self.tmp.name)/'log')
            self.assertEqual(plan['scenes'][0]['narration'],exact)
            with self.assertRaisesRegex(ValueError,'Testo:'):_plan(self.app,{'prompt':'Manim con voce'},[],DEFAULTS|{'_assistant':False},{},threading.Event(),lambda _:None,Path(self.tmp.name)/'log')
    def test_explicit_scene_count_is_checked_before_synthesizing_audio(self):
        from h3chat.narrated_manim import _plan
        wrong=PLAN|{'scenes':PLAN['scenes'][:1]}
        with patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=[(json.dumps(wrong),'stop'),(json.dumps(PLAN),'stop')]) as llm:
            result=_plan(self.app,{'prompt':'Manim con voce in due scene'},[{'role':'user','content':'Manim con voce in due scene','media':[],'status':'done','seq':1}],DEFAULTS,self.model,threading.Event(),lambda _:None,Path(self.tmp.name)/'log')
        self.assertEqual(len(result['scenes']),2);self.assertEqual(llm.call_count,2)
        self.assertEqual(llm.call_args.kwargs['schema']['properties']['scenes']['minItems'],2)

if __name__=='__main__':unittest.main()
