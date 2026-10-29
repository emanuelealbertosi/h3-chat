import json,threading,unittest
from unittest.mock import patch
from test_study import StudyTests as _Study
from h3chat import study_audio,study

class StudyAudioTests(unittest.TestCase):
    setUp=_Study.setUp
    tearDown=_Study.tearDown
    launch=_Study.launch
    execute=_Study.execute
    def test_two_voices_use_saved_script_without_another_llm_call(self):
        chat,job=self.launch(kind='dialogue',count=3);self.execute(job);artifact=self.app.store.canvas_history.get(chat)
        deck=study.decode(artifact['content'])
        for item,speaker in zip(deck['items'],['A','A','B']):item['question']='Conduttore '+speaker
        artifact=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':study.encode(deck),'media':[]},editable=True)
        def configuration(root,settings,prompt):
            return {'engine':'higgs','chunk_chars':280},{},{'prefix':''},{'id':settings['_voice_fields']['gender'],'reference':'fixture.wav','transcript':'Voce'}
        with patch('h3chat.voice.configuration',side_effect=configuration):ticket=study_audio.enqueue(self.app,chat,artifact['id'])
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));requests=[]
        def tool(worker,request,*args,**kwargs):
            requests.append(request);folder=__import__('pathlib').Path(request['output']);(folder/'voce.wav').write_bytes(b'RIFF fixture');return {'duration':5}
        with patch('h3chat.voice.configuration',side_effect=configuration),patch.object(self.app.engine,'tool_call',side_effect=tool),patch.object(self.app.engine,'completion') as llm:self.app.execute_job(job,threading.Event())
        llm.assert_not_called();self.assertEqual([s['voice']['id'] for s in requests[0]['segments']],['male','male','female'])
        latest=self.app.store.canvas_history.get(chat);self.assertEqual(len(latest['media']),1);self.assertEqual(study.decode(latest['content'])['id'],study.decode(artifact['content'])['id']);self.assertEqual(self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],))['status'],'done')
    def test_explaining_a_dialogue_retains_its_existing_audio(self):
        from h3chat.store import uid
        chat,job=self.launch(kind='dialogue',count=2);self.execute(job);artifact=self.app.store.canvas_history.get(chat);deck=study.decode(artifact['content'])
        ident=uid();folder=self.base/'data'/'outputs'/ident;folder.mkdir(parents=True);(folder/'voce.wav').write_bytes(b'RIFF fixture')
        audio=[{'id':ident,'name':'dialogo.wav','mime':'audio/wav','path':f'outputs/{ident}/voce.wav'}]
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':artifact['content'],'media':audio},edit_id=artifact['id'],editable=True)
        ticket=study.explain(self.app,chat,{'artifact_id':saved['id'],'card_id':deck['items'][0]['id']});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));self.execute(job)
        latest=self.app.store.canvas_history.get(chat);self.assertEqual(latest['media'],audio);self.assertTrue((folder/'voce.wav').is_file())

if __name__=='__main__':unittest.main()
