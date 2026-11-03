import json
import unittest
from test_study import StudyTests as _Fixture,completion
from h3chat import study,study_library


class StudyTutorLibraryTests(unittest.TestCase):
    setUp=_Fixture.setUp
    tearDown=_Fixture.tearDown
    launch=_Fixture.launch
    execute=_Fixture.execute

    def test_followup_uses_previous_clarification_and_only_original_sources(self):
        chat,job=self.launch(count=1);self.execute(job)
        value=self.app.store.canvas_history.get(chat);deck=study.decode(value['content']);card=deck['items'][0]
        for question in ('Puoi spiegarlo più semplicemente?','Nel chiarimento precedente cosa significa zuccheri?'):
            ticket=study.explain(self.app,chat,{'artifact_id':value['id'],'card_id':card['id'],'question':question})
            queued=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));calls=[]
            def answer(messages,settings,cancel,**kwargs):
                calls.append(json.loads(messages[1]['content']));return completion(messages,settings,cancel,**kwargs)
            self.execute(queued,complete=answer)
            latest=self.app.store.canvas_history.get(chat);updated=study.decode(latest['content'])
            self.assertEqual(updated['sources'],deck['sources'])
            self.assertEqual(updated['items'][0]['explanation']['question'],question)
            self.assertTrue(updated['items'][0]['explanation']['followup'])
            self.assertIn(question,calls[0]['richiesta'])
            if value['id']!=latest['id'] and card.get('explanation'):self.assertIn(card['explanation']['question'],calls[0]['richiesta'])
            value=latest;card=updated['items'][0]
        with self.assertRaises(ValueError):study.explain(self.app,chat,{'artifact_id':value['id'],'card_id':card['id'],'question':'x'*1201})

    def test_library_is_project_scoped_and_latest_revision_per_chat_set(self):
        project=self.app.knowledge.save({'name':'Studio condiviso'})
        other=self.app.knowledge.save({'name':'Altro progetto'})
        chat,job=self.launch(count=1);self.execute(job)
        self.app.store.execute('UPDATE chats SET project_id=? WHERE id=?',(project['id'],chat))
        value=self.app.store.canvas_history.get(chat);deck=study.decode(value['content'])
        ticket=study.explain(self.app,chat,{'artifact_id':value['id'],'card_id':deck['items'][0]['id']})
        self.execute(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],)))
        latest=self.app.store.canvas_history.get(chat)
        second=self.app.store.create_chat('Seconda chat',project_id=project['id'])['id']
        copied=self.app.store.canvas_history.save(second,{'title':deck['title'],'content':study.encode(deck),'media':[]},editable=True)
        excluded=self.app.store.create_chat('Privata',project_id=other['id'])['id']
        self.app.store.canvas_history.save(excluded,{'title':deck['title'],'content':study.encode(deck),'media':[]},editable=True)
        result=study_library.listing(self.app,chat)
        self.assertEqual(result['scope'],'project');self.assertEqual(len(result['items']),2)
        self.assertEqual({i['id'] for i in result['items']},{latest['id'],copied['id']})
        self.assertTrue(all('content' not in i for i in result['items']))
        self.app.store.execute('UPDATE chats SET project_id=NULL WHERE id=?',(chat,))
        result=study_library.listing(self.app,chat)
        self.assertEqual(result['scope'],'chat');self.assertEqual([i['id'] for i in result['items']],[latest['id']])
