import copy
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_extend import request, inserted_record
from h3chat.video_extension import window
from h3chat.video_routing import direct_plan
from h3chat.video_edit import describe
from h3chat.video_resume import checkpoint
import test_video_edit as fixture


class ExtendTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def worker(self,name,body,*args,**kw):
        if body.get('op')=='frames':
            folder=Path(body['folder']);folder.mkdir(parents=True,exist_ok=True)
            paths=[]
            for i in range(body['frames']):
                p=folder/f'{i}.png';p.write_bytes(b'image');paths.append(str(p))
            return {'paths':paths}
        p=Path(body['output']);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'\0\0\0\x18ftypisomnew')
        return {'duration':body.get('duration',5),'fps':24,'width':640,'height':360}

    def generate(self,model,settings,plan,refs,job,cancel,stage,**kw):
        p=self.app.data/'outputs'/job/'video.mp4';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'\0\0\0\x18ftypisomnew')
        return {'path':p.relative_to(self.app.data).as_posix(),'generation':{'width':640,'height':360,'aspect':'16:9','steps':12,'duration':kw['scene']['duration']}}

    def mux(self,engine,clips,audio,path,*args,**kw):
        path.write_bytes(b'\0\0\0\x18ftypisomnew');return {'duration':kw['audio_duration']}

    def run_mode(self,mode,side='before',duration=5,**extra):
        self.chat,original,refs,outputs,params=self.original();before=copy.deepcopy(self.app.store.settings())
        saved=(self.app.data/'outputs'/original/'scenes.json').read_bytes()
        body={'source':original,'clip':2,'mode':mode,'side':side,'duration':duration,'prompt':'A new scene','assistant':False}|extra
        ident=request(self.app,self.chat,body)['job_id']
        with patch.object(self.app.engine,'tool_call',side_effect=self.worker) as cpu,patch.object(self.app.engine,'generate_video',side_effect=self.generate) as gpu,patch.object(self.app.engine,'refine_video',side_effect=lambda history,prompt,refs,model,settings,*a:(direct_plan(prompt,refs,duration),None)),patch('h3chat.soundtrack.compose',side_effect=self.mux) as mux:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        message=self.app.store.chat(self.chat)['messages'][-1]
        self.assertEqual(message['status'],'done',message['content'])
        record=checkpoint(self.app.data,ident)
        self.assertEqual(self.app.store.settings(),before)
        self.assertEqual((self.app.data/'outputs'/original/'scenes.json').read_bytes(),saved)
        self.assertEqual(record['completed'],4);self.assertEqual(len(record['clip_versions']),4)
        self.assertEqual(mux.call_args.kwargs['audio_duration'],42+duration)
        self.assertEqual(describe(self.app,self.chat,ident)['duration'],42+duration)
        return record,cpu,gpu,refs,outputs

    def test_autonomous_insertion_does_not_inherit_source_or_references(self):
        record,cpu,gpu,refs,outputs=self.run_mode('clip')
        self.assertEqual(gpu.call_args.args[3],[])
        self.assertNotIn('extension_context',gpu.call_args.kwargs['scene'])
        self.assertFalse(any(c.args[1].get('op')=='frames' for c in cpu.call_args_list))
        self.assertEqual(record['outputs'][0],outputs[0]);self.assertEqual(record['outputs'][2:],outputs[1:])
        self.assertEqual([s['start'] for s in record['timeline']],[0,15,20,35])
        audio=next(c.args[1] for c in cpu.call_args_list if c.args[1].get('op')=='audio')
        self.assertEqual((audio['cut'],audio['audio_start'],audio['total']),(15,7,42))

    def test_boundary_images_use_selected_adjacent_frames_and_exact_final_frame(self):
        record,cpu,gpu,refs,outputs=self.run_mode('frames')
        calls=[c.args[1] for c in cpu.call_args_list if c.args[1].get('op')=='frames']
        self.assertEqual([c['source'] for c in calls],[str(self.app.data/outputs[0]),str(self.app.data/outputs[1])])
        self.assertEqual([c['start'] for c in calls],[359/24,0])
        plan=gpu.call_args.args[2];self.assertEqual([p['seconds'] for p in plan['images']],[0,119/24])
        self.assertTrue(all(p['role']=='keyframe' for p in plan['images']))
        self.assertEqual(len(gpu.call_args.args[3]),2)

    def test_native_extension_anchors_five_video_frames_not_an_unrelated_reference(self):
        record,cpu,gpu,refs,outputs=self.run_mode('extension','after',15)
        call=next(c.args[1] for c in cpu.call_args_list if c.args[1].get('op')=='frames')
        self.assertEqual((call['source'],call['start'],call['frames']),(str(self.app.data/outputs[1]),355/24,5))
        context=gpu.call_args.kwargs['scene']['extension_context']
        self.assertEqual(context['side'],'after');self.assertEqual(len(context['paths']),5)
        self.assertEqual(record['outputs'][:2],outputs[:2]);self.assertEqual(record['outputs'][3],outputs[2])
        self.assertEqual(record['extension_context'],context)

    def test_recreation_retains_native_context_and_uses_new_soundtrack_clock(self):
        from h3chat.video_recreate import load
        record,*_=self.run_mode('extension','after',15)
        value=load(self.app,self.chat,record['source'])
        self.assertEqual(value['recipes'][2]['extension_context'],record['extension_context'])
        self.assertEqual([r['plan']['audios'][0]['start'] for r in value['recipes']],[0,15,30,45])
        self.assertTrue(all(r['refs'][-1]['path'].endswith('timeline-audio.wav') for r in value['recipes']))

    def test_invalid_requests_do_not_enqueue(self):
        chat,original,*_=self.original()
        for extra in ({'duration':True},{'duration':7},{'side':'middle'},{'mode':'unknown'},{'mode':'frames','first':'next'},{'assistant':'yes'},{'audio_id':'f'*32},{'mode':'frames','first':'none','last':'none'}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):request(self.app,chat,{'source':original,'clip':1,'mode':'clip','duration':5,'prompt':'New','assistant':False}|extra)
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)

    def test_temporal_context_is_outside_requested_output_duration(self):
        for frames in (120,240,360):
            after=window(frames,'after');before=window(frames,'before')
            self.assertEqual((after['frames'],after['trim_start'],after['guide_start']),(frames+5,5,0))
            self.assertEqual((before['frames'],before['trim_start'],before['guide_start']),(frames+5,0,frames))

    def test_shifted_lazy_clips_keep_exact_original_cache_paths(self):
        from h3chat.video_import import prepare
        chat,ident,refs,outputs,params=self.original()
        value={'record':checkpoint(self.app.data,ident)}
        original=value['record'];original['clip_sources']=[{'path':'uploads/source.mov','start':s['start']} for s in original['timeline']]
        original['timeline'].insert(1,{'index':1,'start':15,'duration':5,'frames':120})
        original['outputs'].insert(1,'outputs/new/inserted.mp4');original['clip_sources'].insert(1,None)
        for i,s in enumerate(original['timeline']):s['index']=i
        with patch.object(self.app.engine,'tool_call',return_value={'clips':3}) as cpu:
            prepare(self.app,value,threading.Event(),lambda _:None,self.app.data/'log')
        calls=[s for c in cpu.call_args_list for s in c.args[1]['timeline']]
        self.assertEqual([s['output'] for s in calls],[str(self.app.data/p) for p in outputs])
        self.assertEqual([s['index'] for s in calls],[0,2,3])
        self.assertEqual([s['start'] for s in calls],[0,15,30])
        self.assertEqual(original['clip_sources'],[None]*4)


if __name__=='__main__':unittest.main()
