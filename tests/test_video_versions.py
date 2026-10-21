"""Version choices use saved footage, retain branches, and never cross chats."""
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_edit import request,describe,source_interval,source
from h3chat.video_assemble import request as assemble
from h3chat.video_resume import checkpoint,save
import test_video_edit as fixture


class VersionTests(unittest.TestCase):
    setUp=fixture.VideoEditTests.setUp
    tearDown=fixture.VideoEditTests.tearDown
    original=fixture.VideoEditTests.original

    def test_stop_preserves_exported_clip_and_discovers_it_from_original_timeline(self):
        from h3chat.downloads import Cancelled
        chat,original,refs,outputs,params=self.original();calls=[]
        original_path=self.app.data/'outputs'/original/'scenes.json';before=original_path.read_bytes()
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            calls.append(job)
            if len(calls)==2:raise Cancelled()
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True)
            path.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':params|{'seed':517890679}}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux) as compose:
            ident=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':'Change jacket'},{'clip':3,'mode':'video','prompt':'Change jacket'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
            self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(ident,))['status'],'cancelled')
            answer=self.app.store.chat(chat)['messages'][-1]
            self.assertEqual(len(answer['media']),1);self.assertTrue(answer['media'][0]['generation']['audio_preserved'])
            self.assertTrue(self.app.store.gallery.get(answer['media'][0]['id'])['path'].endswith('clip-002.mp4'))
            manifest=describe(self.app,chat,original)
            self.assertEqual([len(c['versions']) for c in manifest['clips']],[1,2,1])
            self.assertEqual(manifest['clips'][1]['versions'][1]['seed'],517890679)
            self.assertEqual(compose.call_count,1)
        self.assertEqual(original_path.read_bytes(),before)

    def test_preview_uses_owned_original_audio_with_global_source_offset(self):
        chat,ident,refs,*_=self.original()
        record=checkpoint(self.app.data,ident);record['audio_start']=10;save(self.app.data/'outputs'/ident,record)
        before=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        manifest=describe(self.app,chat,ident)
        self.assertEqual(manifest['preview_audio'],{'url':'/media/'+refs[-1]['path'],'start':10})
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),before)

    def test_branches_preview_choose_edit_and_mount_older_version(self):
        chat,original,refs,outputs,params=self.original();calls=[]
        before=(self.app.data/'outputs'/original/'scenes.json').read_bytes()
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            calls.append(kw['scene']['source_video'])
            target=self.app.data/'outputs'/job/'video.mp4';target.parent.mkdir(parents=True)
            target.write_bytes(b'\0\0\0\x18ftypisomnew')
            return {'path':target.relative_to(self.app.data).as_posix(),'generation':params}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        def run(source_id,versions=None):
            ident=request(self.app,chat,{'source':source_id,'versions':versions,'assistant':False,'remount':False,
                'patches':[{'clip':2,'mode':'video','prompt':'Change the background'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
            self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
            return ident
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux) as compose:
            first=run(original);second=run(original)
            clip=describe(self.app,chat,second)['clips'][1]
            self.assertEqual(len(clip['versions']),3)
            first_path=checkpoint(self.app.data,first)['outputs'][1]
            older=next(v for v in clip['versions'] if v['url']=='/media/'+first_path)
            original_version=clip['versions'][0]
            self.assertIsInstance(older['created'],(int,float))
            self.assertEqual(older['created_source'],'generated')
            self.assertEqual(original_version['created_source'],'file')
            self.assertEqual(original_version['url'],'/media/'+outputs[1])
            third=run(second,{'2':older['id']})
            self.assertEqual(calls[-1]['path'],first_path);self.assertEqual(calls[-1]['start'],0)
            final=assemble(self.app,chat,{'source':third,'versions':{'2':original_version['id']}})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(final,)),threading.Event())
            self.assertEqual(gpu.call_count,3);self.assertEqual(compose.call_args.args[1][1],self.app.data/outputs[1])
            self.assertEqual(checkpoint(self.app.data,final)['selected_versions']['2'],original_version['id'])
            self.assertEqual(len(describe(self.app,chat,final)['clips'][1]['versions']),4)
        self.assertEqual((self.app.data/'outputs'/original/'scenes.json').read_bytes(),before)

    def test_invalid_versions_never_queue_and_other_chat_is_isolated(self):
        chat,ident,*_=self.original();clip=describe(self.app,chat,ident)['clips'][0]
        for selected in ([],{'0':clip['selected_version']},{'01':clip['selected_version']},{'1':'made-up'},{'4':clip['selected_version']}):
            with self.subTest(selected=selected),self.assertRaises(ValueError):
                request(self.app,chat,{'source':ident,'versions':selected,'assistant':False,'patches':[{'clip':1,'prompt':'Change background'}]})
        other,other_id,*_=self.original()
        with self.assertRaises(ValueError):request(self.app,other,{'source':other_id,'versions':{'1':clip['selected_version']},'patches':[{'clip':1,'prompt':'Change background'}]})
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),2)

    def test_partial_variant_is_full_clip_and_splice_uses_chosen_base(self):
        chat,original,refs,outputs,params=self.original()
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            target=self.app.data/'outputs'/job/'video.mp4';target.parent.mkdir(parents=True)
            target.write_bytes(b'\0\0\0\x18ftypisomnew');return {'path':target.relative_to(self.app.data).as_posix(),'generation':params}
        def splice(worker,body,*args,**kw):
            Path(body['output']).write_bytes(b'\0\0\0\x18ftypisomspliced');return {'frames':360}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=splice) as splicing,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            first=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':'Red jacket','start':2,'end':6}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(first,)),threading.Event())
            clip=describe(self.app,chat,first)['clips'][1]
            self.assertEqual(len(clip['versions']),2)
            self.assertTrue(clip['versions'][1]['url'].endswith('/edited.mp4'))
            second=request(self.app,chat,{'source':first,'versions':{'2':clip['versions'][0]['id']},'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':'Blue jacket','start':7,'end':9}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(second,)),threading.Event())
            self.assertEqual(splicing.call_args.args[1]['original'],str(self.app.data/outputs[1]))
            self.assertEqual(len(describe(self.app,chat,second)['clips'][1]['versions']),3)

    def test_old_whole_clip_exports_are_available_from_original(self):
        chat,original,refs,outputs,params=self.original()
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            target=self.app.data/'outputs'/job/'video.mp4';target.parent.mkdir(parents=True)
            target.write_bytes(b'\0\0\0\x18ftypisomnew');return {'path':target.relative_to(self.app.data).as_posix(),'generation':params}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux) as compose:
            first=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':'Red jacket'}]})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(first,)),threading.Event())
            record=checkpoint(self.app.data,first)
            for key in ('working_timeline','clip_versions','selected_versions'):record.pop(key,None)
            record['outputs']=outputs.copy();save(self.app.data/'outputs'/first,record)
            manifest=describe(self.app,chat,original)
            self.assertEqual([len(c['versions']) for c in manifest['clips']],[1,2,1])
            old=manifest['clips'][1]['versions'][1]
            self.assertIn(first,old['url']);self.assertEqual(old['preview_start'],0)
            final=assemble(self.app,chat,{'source':original,'versions':{'2':old['id']}})['job_id']
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(final,)),threading.Event())
            self.assertEqual(gpu.call_count,1);self.assertIn(first,str(compose.call_args.args[1][1]))

    def test_sibling_images_are_remapped_without_changing_identity(self):
        chat,original,refs,outputs,params=self.original()
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            target=self.app.data/'outputs'/job/'video.mp4';target.parent.mkdir(parents=True)
            target.write_bytes(b'\0\0\0\x18ftypisomnew');return {'path':target.relative_to(self.app.data).as_posix(),'generation':params}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\0\0\0\x18ftypisomfinal');return {'duration':kw['audio_duration']}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',side_effect=mux):
            ids=[]
            for label in ('red','blue'):
                target=self.app.data/'uploads'/f'{label}.png';target.write_bytes(b'synthetic')
                media={'id':('a' if label=='red' else 'b')*32,'name':label+'.png','path':target.relative_to(self.app.data).as_posix(),'mime':'image/png'}
                self.app.store.gallery.register([media])
                media_id=media['id'];manifest=describe(self.app,chat,original);known=next((r['index'] for r in manifest['images'] if r['id']==media_id),None)
                n=known or len(manifest['images'])+1
                ident=request(self.app,chat,{'source':original,'assistant':False,'remount':False,'media':[{'id':media_id}],'patches':[{'clip':2,'mode':'video','prompt':f'Use <Picture {n}> jacket','images':[n]}]})['job_id']
                self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event());ids.append(ident)
            manifest=describe(self.app,chat,ids[-1]);old=next(v for v in manifest['clips'][1]['versions'] if v['url'].endswith(ids[0]+'/scene-002/video.mp4'))
            blue=next(r for r in manifest['images'] if r['id']=='b'*32);red=next(r for r in manifest['images'] if r['id']=='a'*32)
            self.assertNotEqual(blue['index'],red['index']);self.assertIn(f"<Picture {red['index']}>",old['prompt'])
            selected=request(self.app,chat,{'source':ids[-1],'versions':{'2':old['id']},'assistant':False,'remount':False,'patches':[{'clip':2,'mode':'video','prompt':f"Use <Picture {red['index']}>",'images':[red['index']]}]})['job_id']
            payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(selected,))['payload'])
            self.assertEqual(payload['media'][red['index']-1]['id'],'a'*32)


if __name__=='__main__':unittest.main()
