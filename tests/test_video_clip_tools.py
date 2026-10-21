import copy
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_clip_tools import request, target, prepare_infographic, signature, record_render, use_infographic
from h3chat.video_edit import describe
from h3chat.video_resume import checkpoint
from h3chat.video_assemble import request as assemble
from h3chat.slides import encode
import test_video_edit as fixture


class ClipToolTests(unittest.TestCase):
    setUp = fixture.VideoEditTests.setUp
    tearDown = fixture.VideoEditTests.tearDown
    original = fixture.VideoEditTests.original

    def replacement(self):
        media={'id':'a'*32,'name':'Edited.mp4','path':'uploads/replacement.mp4','mime':'video/mp4'}
        (self.app.data/media['path']).write_bytes(b'\0\0\0\x18ftypisomreplacement')
        self.app.store.gallery.register([media])
        return media

    def worker(self, worker, body, *args, **kw):
        output=Path(body['output']);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_bytes(b'\0\0\0\x18ftypisomnew')
        return {'duration':body.get('frames',body.get('total_frames',360))/24,'fps':24,
                'width':body.get('width',640),'height':body.get('height',360)}

    def mux(self, engine, clips, audio, output, *args, **kw):
        output.write_bytes(b'\0\0\0\x18ftypisommux')
        return {'duration':kw['audio_duration']}

    def run_job(self, ident):
        self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        message=self.app.store.chat(self.chat)['messages'][-1]
        self.assertEqual(message['status'],'done',message['content'])
        return message

    def test_export_selected_interval_and_audio_are_exact_without_gpu_or_preset_changes(self):
        self.chat,original,refs,outputs,*_=self.original()
        previous=(self.app.data/'outputs'/original/'scenes.json').read_bytes()
        settings=copy.deepcopy(self.app.store.settings())
        ident=request(self.app,self.chat,{'action':'export','source':original,'clip':2,'start':2,'end':7})['job_id']
        with patch.object(self.app.engine,'tool_call',side_effect=self.worker) as worker,patch.object(self.app.engine,'generate_video') as gpu:
            result=self.run_job(ident)
        body=worker.call_args.args[1]
        self.assertEqual(body['source'],str(self.app.data/outputs[1]))
        self.assertEqual((body['start'],body['frames'],body['audio_start']),(2,120,24))
        self.assertEqual(body['audio'],str(self.app.data/refs[-1]['path']))
        self.assertEqual(result['media'][0]['generation']['duration'],5)
        self.assertTrue(self.app.store.gallery.get(result['media'][0]['id']))
        gpu.assert_not_called()
        self.assertEqual(self.app.store.settings(),settings)
        self.assertEqual((self.app.data/'outputs'/original/'scenes.json').read_bytes(),previous)

    def test_partial_replacement_versions_preview_and_montage_reuse_original_audio(self):
        self.chat,original,refs,outputs,*_=self.original();media=self.replacement()
        ident=request(self.app,self.chat,{'action':'replace','source':original,'clip':2,'start':3,'end':6,'media_id':media['id']})['job_id']
        with patch.object(self.app.engine,'tool_call',side_effect=self.worker) as worker,patch('h3chat.soundtrack.compose',side_effect=self.mux) as mux,patch.object(self.app.engine,'generate_video') as gpu:
            message=self.run_job(ident)
            clip=describe(self.app,self.chat,original)['clips'][1]
            self.assertEqual(len(clip['versions']),2)
            self.assertIn('Video importato',clip['versions'][1]['label'])
            final=assemble(self.app,self.chat,{'source':original,'versions':{'2':clip['versions'][1]['id']}})['job_id']
            self.run_job(final)
        self.assertEqual(worker.call_args_list[0].args[1]['frames'],72)
        splice=worker.call_args_list[1].args[1]
        self.assertEqual((splice['start_frame'],splice['end_frame'],splice['total_frames']),(72,144,360))
        self.assertEqual(splice['original'],str(self.app.data/outputs[1]))
        self.assertEqual(mux.call_args_list[0].kwargs['audio_start'],22)
        self.assertEqual(mux.call_args_list[-1].kwargs['audio_start'],7)
        self.assertEqual(mux.call_args_list[-1].kwargs['audio_duration'],42)
        self.assertEqual(mux.call_args_list[-1].args[1][0],self.app.data/outputs[0])
        self.assertEqual(message['media'][0]['generation']['timeline_id'],ident)
        self.assertEqual(checkpoint(self.app.data,ident)['completed'],3)
        gpu.assert_not_called()

    def test_invalid_ranges_foreign_versions_and_files_do_not_queue(self):
        chat,original,*_=self.original();other,foreign,*_=self.original()
        owned=describe(self.app,chat,original)['clips'][0]['selected_version']
        for extra in ({'clip':0},{'clip':True},{'start':-1,'end':2},{'start':2,'end':16},
                      {'start':float('nan'),'end':3},{'start':2},{'versions':{'1':'foreign-version'}}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                request(self.app,chat,{'action':'export','source':original,'clip':1}|extra)
        with self.assertRaises(ValueError):target(self.app,other,{'source':foreign,'clip':1,'versions':{'1':owned}})
        with self.assertRaises(ValueError):request(self.app,chat,{'action':'replace','source':original,'clip':1,'media_id':'f'*32})
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),2)

    def test_uploaded_lazy_timeline_exports_only_selected_global_interval(self):
        self.chat,*_=self.original();media=self.replacement()
        cache=self.app.data/'outputs/import-fixture';cache.mkdir()
        (cache/'audio.wav').write_bytes(b'synthetic audio')
        images=[]
        for i in range(4):
            path=cache/f'guide-{i}.png';path.write_bytes(b'synthetic guide')
            images.append({'id':str(i+4)*32,'path':str(path)})
        info={'duration':35,'width':1920,'height':1080,'images':images,'audio_id':'9'*32}
        with patch('h3chat.video_import.metadata',return_value=(cache,info)),patch.object(self.app.engine,'tool_call',side_effect=self.worker) as worker:
            ident=request(self.app,self.chat,{'action':'export','source':media['id'],'segment_seconds':10,'clip':3,'start':2,'end':5})['job_id']
            self.run_job(ident)
        body=worker.call_args.args[1]
        self.assertEqual(body['source'],str(self.app.data/media['path']))
        self.assertEqual((body['start'],body['audio_start'],body['frames']),(22,22,72))
        self.assertEqual((body['width'],body['height']),(1920,1080))
        worker.assert_called_once()
        self.assertFalse(any(cache.glob('clip-*.mp4')))

    def test_infographic_uses_exact_short_interval_and_keeps_input_snapshot(self):
        self.chat,original,*_=self.original()
        with patch.object(self.app.engine,'require_model',return_value={'name':'Synthetic chat'}):
            ident=request(self.app,self.chat,{'action':'infographic','source':original,'clip':2,'start':1,'end':3,
                'prompt':'Split screen, title at 0.5 seconds','infographic':{'layout':'columns2'}})['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload']);settings=payload['settings']
        with patch.object(self.app.engine,'tool_call',side_effect=self.worker) as worker:
            item,command=None,None
            item=prepare_infographic(self.app,{'id':ident,'chat_id':self.chat},settings,threading.Event(),lambda _:None,None)
        self.assertTrue(payload['canvas']);self.assertEqual(settings['_infographic']['format'],'16:9')
        self.assertEqual(settings['_infographic']['layout'],'columns2')
        self.assertFalse(settings['_infographic']['voice']);self.assertEqual(settings['_infographic']['video_audio'],'keep')
        self.assertEqual(settings['_video_clip_target']['end']-settings['_video_clip_target']['start'],2)
        self.assertEqual(settings['_infographic']['video_id'],item['id'])
        self.assertEqual(worker.call_args.args[1]['frames'],48)

    def test_shared_job_dispatch_passes_export_to_existing_infographic_engine(self):
        self.chat,original,*_=self.original()
        with patch.object(self.app.engine,'require_model',return_value={'name':'Synthetic LLM'}):
            ident=request(self.app,self.chat,{'action':'infographic','source':original,'clip':2,'start':1,'end':3,
                'prompt':'Titolo al secondo 0.4, usando il filmato selezionato.'})['job_id']
            def tools(history,payload,*args,**kwargs):return history,{},[],[]
            def build(app,job,payload,history,settings,*args):
                self.assertEqual(len(payload['media']),1)
                self.assertTrue(payload['media'][0]['path'].endswith('/spezzone.mp4'))
                self.assertEqual(history[-1]['media'][0]['id'],payload['media'][0]['id'])
                self.assertEqual(settings['_video_clip_target']['render_size'],[640,360])
                self.assertEqual(settings['_video_clip_target']['start'],1)
                return {'title':'Synthetic','content':'','media':[]}
            with patch.object(self.app.engine,'tool_call',side_effect=self.worker),patch.object(self.app.engine,'prepare_tools',side_effect=tools),patch.object(self.app.engine,'prepare'),patch('h3chat.infographics.build',side_effect=build) as renderer:
                self.run_job(ident)
                renderer.assert_called_once()

    def test_canvas_requires_matching_render_even_after_media_canonicalization(self):
        self.chat,original,*_=self.original();media=self.replacement()
        _,command=target(self.app,self.chat,{'source':original,'clip':1})
        deck={'version':1,'engine':'llm','title':'Overlay','format':'16:9','pages':[
            {'title':'Overlay','html':'<html><body><p>Hello</p></body></html>','status':'ready','sources':[]}],
            'infographic':{'version':1,'durations':[15],'transition':'cut','sfx':'none','timeline_target':command}}
        record_render(self.app.data/media['path'],deck)
        artifact=self.app.store.canvas_history.save(self.chat,{'title':deck['title'],'content':encode(deck),'media':[media]},editable=True)
        with patch('h3chat.video_clip_tools.request',return_value={'job_id':'synthetic'}) as queued:
            use_infographic(self.app,self.chat,{'artifact_id':artifact['id']})
            self.assertEqual(queued.call_args.args[2]['media_id'],media['id'])
            deck['pages'][0]['html']='<html><body><p>Changed</p></body></html>'
            self.app.store.canvas_history.save(self.chat,{'title':deck['title'],'content':encode(deck),'media':[media]},edit_id=artifact['id'],editable=True)
            with self.assertRaisesRegex(ValueError,'Esporta / aggiorna'):use_infographic(self.app,self.chat,{'artifact_id':artifact['id']})
            self.assertEqual(queued.call_count,1)


if __name__=='__main__':unittest.main()
