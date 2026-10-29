import ast,json,subprocess,sys,threading,unittest
from pathlib import Path
from unittest.mock import patch
from test_tools import ToolsTests as _Tools
from h3chat import study_import

class StudyImportTests(unittest.TestCase):
    setUp=_Tools.setUp
    tearDown=_Tools.tearDown
    def launch(self,body):
        project=self.app.knowledge.save({'name':'Notebook','sources_only':True});other=self.app.knowledge.save({'name':'Altro'})
        ticket=study_import.enqueue_project(self.app,project['id'],body)
        return project,other,self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
    def test_public_page_is_cleaned_indexed_and_isolated(self):
        project,other,job=self.launch({'kind':'web','name':'Pagina sulle piante','url':'https://example.com/plants'})
        with patch('h3chat.web_search.fetch',return_value='<html><script>segreto non fonte</script><h1>Fotosintesi</h1><p>Le piante producono ossigeno e zuccheri usando la luce del sole.</p></html>'):
            self.app.execute_job(job,threading.Event())
        row=self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],));self.assertEqual(row['status'],'done',row)
        source=self.app.knowledge.project(project['id'])['sources'][0];self.assertEqual(source['source_url'],'https://example.com/plants');self.assertEqual(source['status'],'ready')
        chunks=self.app.store.all('SELECT text FROM rag_chunks WHERE source_id=?',(source['id'],));self.assertIn('Fotosintesi',chunks[0]['text']);self.assertNotIn('segreto',chunks[0]['text']);self.assertEqual(self.app.knowledge.project(other['id'])['sources'],[])
    def test_youtube_import_uses_caption_worker_only_and_keeps_url_and_time(self):
        project,other,job=self.launch({'kind':'youtube','name':'Lezione','url':'https://youtu.be/abcdefghijk'})
        with patch.object(self.app.engine,'tool_call',return_value={'title':'Lezione di botanica','language':'it','text':'[12.0 s] Le piante producono ossigeno e zuccheri grazie alla fotosintesi.'}) as tool,patch.object(self.app.engine,'transcribe') as asr:
            self.app.execute_job(job,threading.Event())
        self.assertEqual(tool.call_args.args[0],'study-captions-worker.py');asr.assert_not_called();source=self.app.knowledge.project(project['id'])['sources'][0];self.assertIn('youtube.com',source['source_url']);self.assertIn('[12.0 s]',Path(source['path']).read_text(encoding='utf8'))
    def test_reimported_url_never_silently_reports_stale_content_as_updated(self):
        project,other,job=self.launch({'kind':'web','name':'Pagina sulle piante','url':'https://example.com/plants'})
        with patch('h3chat.web_search.fetch',return_value='<p>La prima versione documenta la fotosintesi e la produzione di ossigeno nelle piante.</p>'):
            self.app.execute_job(job,threading.Event())
        with patch('h3chat.web_search.fetch') as fetch:
            with self.assertRaisesRegex(ValueError,'già importato'):
                study_import.enqueue_project(self.app,project['id'],{'kind':'web','name':'Pagina aggiornata','url':'https://example.com/plants'})
            fetch.assert_not_called()
        self.assertEqual(len(self.app.knowledge.project(project['id'])['sources']),1)
        chunks=self.app.store.all('SELECT c.text FROM rag_chunks c JOIN project_sources s ON s.id=c.source_id WHERE s.project_id=?',(project['id'],))
        self.assertIn('prima versione',' '.join(c['text'] for c in chunks))
    def test_video_import_reuses_whisper_and_preserves_original(self):
        import base64
        from h3chat.store import uid
        ident=uid();path=self.data/'uploads'/ident/'lecture.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'video fixture')
        media={'id':ident,'name':'lecture.mp4','path':path.relative_to(self.data).as_posix(),'mime':'video/mp4'};self.app.store.gallery.register([media],'uploaded')
        project,other,job=self.launch({'kind':'audio','name':'Lezione video','asset_id':ident})
        result={'text':'La fotosintesi usa luce.','segments':[{'start':1,'end':3,'text':'La fotosintesi usa luce e produce zuccheri.'}]}
        with patch.object(self.app.engine,'transcribe',return_value=result) as asr:self.app.execute_job(job,threading.Event())
        asr.assert_called_once();source=self.app.knowledge.project(project['id'])['sources'][0];self.assertEqual(source['status'],'ready');self.assertIn('[1.0–3.0 s]',Path(source['path']).read_text(encoding='utf8'));self.assertTrue(path.is_file());self.assertEqual(self.app.store.one('SELECT media_id FROM rag_media_origins WHERE source_id=?',(source['id'],))['media_id'],ident)
        self.assertEqual(study_import.origin(self.app,project['id'],source['id'])['media']['id'],ident)
        self.assertIsNone(study_import.origin(self.app,other['id'],source['id'])['media'])
    def test_explicit_transcribe_accepts_video_without_image_generation_or_llm(self):
        from h3chat.store import uid
        ident=uid();path=self.data/'uploads'/ident/'lecture.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'video fixture')
        media={'id':ident,'name':'lecture.mp4','path':path.relative_to(self.data).as_posix(),'mime':'video/mp4'};self.app.store.gallery.register([media],'uploaded')
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':'Trascrivi il video','media':[media],'transcribe':True,'rag':False})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));result={'text':'Parlato','language':'it','duration':3,'device':'cpu','compute_type':'int8','segments':[{'start':1,'end':3,'text':'Parlato'}]}
        with patch.object(self.app.engine,'transcribe',return_value=result) as asr,patch.object(self.app.engine,'start_llama') as llm,patch.object(self.app.engine,'generate_video') as video:self.app.execute_job(job,threading.Event())
        asr.assert_called_once();llm.assert_not_called();video.assert_not_called();self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],))['status'],'done')
    def test_cancelled_media_batch_keeps_only_completed_sources_and_originals(self):
        from h3chat.store import uid
        assets=[]
        for index in range(2):
            ident=uid();path=self.data/'uploads'/ident/f'lecture-{index}.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'video fixture')
            assets.append({'id':ident,'name':path.name,'path':path.relative_to(self.data).as_posix(),'mime':'video/mp4'})
        self.app.store.gallery.register(assets,'uploaded')
        project,other,job=self.launch({'kind':'audio','name':'Lezioni','asset_ids':[m['id'] for m in assets]});cancel=threading.Event();calls=[]
        def transcribe(*args,**kw):
            calls.append(1)
            if len(calls)==2:cancel.set()
            return {'text':'La fotosintesi utilizza luce e acqua.','segments':[{'start':0,'end':3,'text':'La fotosintesi utilizza luce e acqua e produce ossigeno nelle piante.'}]}
        with patch.object(self.app.engine,'transcribe',side_effect=transcribe):self.app.execute_job(job,cancel)
        sources=self.app.knowledge.project(project['id'])['sources'];self.assertEqual(len(sources),1);self.assertEqual(sources[0]['status'],'ready')
        self.assertEqual(study_import.origin(self.app,project['id'],sources[0]['id'])['media']['id'],assets[0]['id'])
        self.assertTrue(all((self.data/m['path']).is_file() for m in assets));self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],))['status'],'cancelled')
    def test_native_video_audio_decoder_runs_on_cpu(self):
        # Execute only the existing bounded decoder, not the worker's IPC loop/model.
        import shutil
        ffmpeg=shutil.which('ffmpeg') or ('C:/ffmpeg/bin/ffmpeg.exe' if Path('C:/ffmpeg/bin/ffmpeg.exe').is_file() else None)
        if not ffmpeg:self.skipTest('FFmpeg not installed')
        path=self.data/'sample.mp4';subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=black:s=32x32:d=0.3','-f','lavfi','-i','sine=frequency=440:duration=0.3','-c:v','libx264','-c:a','aac','-shortest',str(path)],check=True,capture_output=True)
        source=Path(__file__).resolve().parents[1]/'native/transcription-worker.py';tree=ast.parse(source.read_text(encoding='utf8'));function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='audio');scope={};exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),scope)
        values=scope['audio'](str(path));self.assertGreater(len(values),3000);self.assertEqual(values.dtype.name,'float32');self.assertGreater(float(abs(values).max()),.01)

import test_access as access_fixture

class GuestStudyImportHttpTests(unittest.TestCase):
    setUp=access_fixture.AccessHttpTests.setUp
    tearDown=access_fixture.AccessHttpTests.tearDown
    request=access_fixture.AccessHttpTests.request
    setup_owner=access_fixture.AccessHttpTests.setup_owner
    def test_guest_media_import_is_post_only_authenticated_and_workspace_scoped(self):
        from h3chat.workspaces import guest_allowed
        owner_csrf=self.setup_owner();status,guest,_=self.request('/api/auth/users',{'name':'amico','password':access_fixture.PASSWORD},client=self.owner,csrf=owner_csrf);self.assertEqual(status,201)
        self.request('/api/auth/login',{'name':'amico','password':access_fixture.PASSWORD},client=self.guest);guest_csrf=self.request('/api/auth/me',client=self.guest)[1]['csrf']
        status,project,_=self.request('/api/projects',{'name':'Progetto ospite'},client=self.guest,csrf=guest_csrf);self.assertEqual(status,201)
        owner_project=self.app.knowledge.save({'name':'Privato proprietario'});path='/api/projects/'+project['id']+'/media-import';body={'kind':'web','name':'Piante','url':'https://example.com/plants'}
        self.assertTrue(guest_allowed(path,'POST'));self.assertFalse(guest_allowed(path,'PATCH'));self.assertFalse(guest_allowed(path,'DELETE'))
        self.assertEqual(self.request(path,body)[0],401);self.assertEqual(self.request(path,body,client=self.guest)[0],403)
        self.assertEqual(self.request('/api/projects/'+owner_project['id']+'/media-import',body,client=self.guest,csrf=guest_csrf)[0],400)
        self.assertEqual(self.request(path,body,method='PATCH',client=self.guest,csrf=guest_csrf)[0],403)
        self.assertEqual(self.request(path,body,method='DELETE',client=self.guest,csrf=guest_csrf)[0],403)
        status,ticket,_=self.request(path,body,client=self.guest,csrf=guest_csrf);self.assertEqual(status,202,ticket)
        guest_app=self.server.workspaces.items[guest['id']];job=guest_app.store.one('SELECT payload,status FROM jobs WHERE id=?',(ticket['job_id'],));self.assertEqual(job['status'],'queued');self.assertEqual(json.loads(job['payload'])['project_id'],project['id'])
        self.assertEqual(self.app.store.all('SELECT id FROM jobs'),[]);self.assertEqual(self.app.knowledge.project(owner_project['id'])['sources'],[])

if __name__=='__main__':unittest.main()
