"""Timeline/queue integration in temporary stores; no user database or GPU."""
import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_options import validate,options
from h3chat.video_edit import request
from h3chat.video_resume import checkpoint,save
from h3chat.video_longtake import attach,stale_contexts
import test_video_edit as fixture


class LongTakeTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def test_off_by_default_and_strict_opt_in(self):
        self.assertFalse(validate({})['longtake_enabled'])
        for value in (1,'yes',None):
            with self.assertRaises(ValueError):validate({'longtake_enabled':value})
        with self.assertRaisesRegex(ValueError,'PDD'):validate({'longtake_enabled':True,'pdd_enabled':True})
        before=copy.deepcopy(self.app.store.settings());chat=self.app.store.create_chat()['id']
        job=self.app.send(chat,{'prompt':'Video','video':True,'assistant':False,'video_parameters':{'longtake_enabled':True}})['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])
        self.assertTrue(options(self.model,payload['settings'],False)['longtake_enabled'])
        self.assertEqual(before,self.app.store.settings())

    def test_single_clip_edit_uses_selected_predecessor_without_regenerating_neighbours(self):
        chat,original,refs,outputs,p=self.original();record=checkpoint(self.app.data,original)
        context=self.app.data/'outputs'/original/'scene-001/longtake-tail.safetensors';context.write_bytes(b'CPU fixture')
        record['parameters'][0]=p|{'longtake':{'context_file':context.relative_to(self.app.data).as_posix()}}
        save(context.parent.parent,record);before=(context.parent.parent/'scenes.json').read_bytes()
        ident=request(self.app,chat,{'source':original,'assistant':False,'parameters':{'longtake_enabled':True},
            'patches':[{'clip':2,'prompt':'Camera continues moving slowly'}]})['job_id'];calls=[]
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            calls.append(kw['scene']);self.assertTrue(options(model,settings,False)['longtake_enabled'])
            self.assertEqual(kw['scene']['longtake_context'],str(context))
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':p|{'longtake_enabled':True,'longtake':{'context_source':str(context)}}}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(len(calls),1);updated=checkpoint(self.app.data,ident)
        self.assertEqual(updated['outputs'][::2],outputs[::2])
        self.assertEqual((context.parent.parent/'scenes.json').read_bytes(),before)
        self.assertEqual(updated['revision_plans']['2']['audios'][0]['start'],22)

    def test_changing_predecessor_marks_only_advisory_dependency(self):
        tail=self.folder/'tail.safetensors';tail.write_bytes(b'fixture')
        p={'longtake':{'context_file':'tail.safetensors'}}
        self.assertEqual(attach(self.folder,{},p),{'longtake_context':str(tail)})
        record={'parameters':[p,{'longtake':{'context_source':str(tail)}}]}
        self.assertEqual(stale_contexts(self.folder,record),[])
        record['parameters'][0]={}
        self.assertEqual(stale_contexts(self.folder,record),[2])

    def test_long_sequence_continues_from_saved_context_after_interruption(self):
        chat,original,refs,outputs,p=self.original();plan=checkpoint(self.app.data,original)['plan']
        settings=self.app.store.settings()|{'_assistant':False,'_video_duration':40,'_video_soundtrack':refs[-1],
            '_video_audio_start':7,'_video_audio_source_duration':60,
            'video_overrides':{self.model['id']:{'longtake_enabled':True}}}
        calls=[]
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            scene=kw['scene'];calls.append(copy.deepcopy(scene))
            if len(calls)==2:raise RuntimeError('Synthetic interrupted second clip')
            f=self.app.data/'outputs'/job;f.mkdir(parents=True);(f/'video.mp4').write_bytes(b'\0\0\0\x18ftypisomnew')
            (f/'longtake-tail.safetensors').write_bytes(b'fixture')
            return {'path':(f/'video.mp4').relative_to(self.app.data).as_posix(),'generation':p|{'longtake_enabled':True,
                'longtake':{'context_file':(f/'longtake-tail.safetensors').relative_to(self.app.data).as_posix()}}}
        ident='a'*32;new='b'*32
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.compose',return_value={'duration':40}):
            with self.assertRaisesRegex(RuntimeError,'interrupted'):
                self.app.engine.generate_long_video(self.model,settings,plan,refs,ident,threading.Event(),lambda x:None,prompt='Continuous walking')
            saved=checkpoint(self.app.data,ident);self.assertEqual(saved['completed'],1)
            self.assertIn('longtake_context',calls[1])
            result=self.app.engine.generate_long_video(self.model,settings|{'_video_resume':ident},plan,refs,new,threading.Event(),lambda x:None,prompt='Continuous walking')
        self.assertEqual([c['index'] for c in calls],[0,1,1,2])
        self.assertEqual(calls[1]['longtake_context'],calls[2]['longtake_context'])
        self.assertEqual(result['generation']['duration'],40)
        self.assertEqual(checkpoint(self.app.data,new)['outputs'][0],saved['outputs'][0])


if __name__=='__main__':unittest.main()
