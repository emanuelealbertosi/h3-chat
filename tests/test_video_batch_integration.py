import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_edit import request,describe,source
from h3chat.video_resume import checkpoint
from h3chat.video_batch import finish_standalone
import test_video_edit as fixture

class BatchIntegrationTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def test_first_chat_send_saves_prompt_batch_even_with_automatic_video_routing(self):
        chat=self.app.store.create_chat()['id'];before=copy.deepcopy(self.app.store.settings())
        ident=self.app.send(chat,{'prompt':'Crea un video con 3 versioni dell’intero video.','assistant':False})['job_id']
        p=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])
        preset=p['settings']['video_overrides'][self.model['id']]
        self.assertEqual((preset['variants'],preset['variants_mode']),(3,'video'))
        self.assertEqual(self.app.store.settings(),before)

    def test_partial_edit_keeps_three_full_alternatives_and_splices_same_source(self):
        chat,original,refs,outputs,params=self.original();splices=[]
        def generate(model,settings,plan,selected,job,cancel,stage,**kw):
            takes=[]
            for i in range(3):
                p=self.app.data/'outputs'/job/f'variant-{i+1}/video.mp4';p.parent.mkdir(parents=True);p.write_bytes(b'\0\0\0\x18ftypisom'+bytes([i]))
                takes.append({'path':p.relative_to(self.app.data).as_posix(),'generation':params|{'seed':10+i,'variant_index':i+1,'variants':3,'variants_mode':'clip','variant_batch_id':job.split('/')[0]}})
            return copy.deepcopy(takes[0])|{'batch_variants':takes}
        def worker(name,body,*a,**kw):
            if name=='video-splice-worker.py':splices.append(copy.deepcopy(body))
            p=Path(body['output']);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'\0\0\0\x18ftypisommerged')
            return {'frames':360}
        def mux(engine,clips,audio,target,*a,**kw):target.write_bytes(b'\0\0\0\x18ftypisom');return {'duration':kw['audio_duration']}
        ident=request(self.app,chat,{'source':original,'assistant':False,'parameters':{'variants':3},'patches':[{'clip':2,'prompt':'New jacket','start':2,'end':7}]})['job_id']
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=worker),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        saved=checkpoint(self.app.data,ident);self.assertEqual(saved['revision_completed'],[2])
        self.assertEqual(len(splices),3);self.assertEqual(len({s['output'] for s in splices}),3)
        self.assertEqual({s['original'] for s in splices},{str(self.app.data/outputs[1])})
        versions=describe(self.app,chat,ident)['clips'][1]['versions'];new=[v for v in versions if v.get('variant_index')]
        self.assertEqual([v['seed'] for v in new],[10,11,12])
        self.assertEqual(len({v['url'] for v in new}),3)
        self.assertEqual(saved['selected_versions']['2'],new[0]['id'])
        self.assertEqual(saved['timeline'][1]['frames'],360)

    def test_short_batch_timeline_uses_each_selected_generated_audio(self):
        chat,original,refs,outputs,params=self.original()
        takes=[]
        for i in range(3):
            p=self.app.data/'outputs'/original/f'batch-{i}/video.mp4';p.parent.mkdir(parents=True);p.write_bytes(b'\0\0\0\x18ftypisom')
            takes.append({'path':p.relative_to(self.app.data).as_posix(),'generation':params|{'seed':20+i,'variant_index':i+1,'variants':3,'variants_mode':'clip','variant_batch_id':original}})
        plan={'prompt':'Standalone shot','images':[],'audios':[]}
        record={'batch_standalone':True,'timeline':[{'index':0,'start':0,'duration':15,'frames':360,'images':[]}],'prompts':['Standalone shot'],'parameters':[],'outputs':[],'completed':0,'plan':plan,'model':self.model['id']}
        item=copy.deepcopy(takes[0])|{'batch_variants':takes,'batch_standalone_record':record}
        def audio_worker(name,body,*a,**kw):Path(body['output']).write_bytes(b'RIFFwave');return {'source_audio':True}
        with patch.object(self.app.engine,'tool_call',side_effect=audio_worker):global_plan,global_refs=finish_standalone(self.app,item,plan,[],{'id':original},threading.Event(),lambda _:None,self.app.data/'log')
        saved=checkpoint(self.app.data,original)
        self.assertEqual(len(saved['clip_versions'][0]),3);self.assertEqual(global_plan['audios'][0]['role'],'reuse')
        value={'record':saved,'images':[],'refs':global_refs,'audio':global_refs[-1]}
        from h3chat.video_versions import apply
        alternative=saved['clip_versions'][0][2];apply(value,{'1':alternative['id']},self.app.data)
        self.assertEqual(value['audio']['path'],alternative['audio']['path'])
        self.assertEqual(value['refs'][-1]['id'],alternative['audio']['id'])
        self.assertEqual(saved['outputs'][0],alternative['output'])

if __name__=='__main__':unittest.main()
