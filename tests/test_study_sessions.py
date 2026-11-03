import copy
import unittest
from unittest.mock import patch
from test_study import StudyTests as _Fixture
from h3chat import study


class StudySessionTests(unittest.TestCase):
    setUp=_Fixture.setUp
    tearDown=_Fixture.tearDown
    launch=_Fixture.launch
    execute=_Fixture.execute

    def test_schedule_persists_advances_and_resets_without_losing_reviews(self):
        chat,job=self.launch(count=1);self.execute(job)
        value=self.app.store.canvas_history.get(chat);deck=study.decode(value['content']);card=deck['items'][0]
        moment=2_000_000_000
        for index,days in enumerate((1,3,7,14,30,30)):
            with patch('h3chat.study.time.time',return_value=moment):
                result=study.progress(self.app,chat,value['id'],{'card_id':card['id'],'remembered':True})['items'][card['id']]
                self.assertEqual(result['attempts'],index+1)
                self.assertEqual(result['next_review'],moment+days*86400)
                self.assertFalse(result['due_now'])
            with patch('h3chat.study.time.time',return_value=result['next_review']):
                self.assertTrue(study.progress(self.app,chat,value['id'])['items'][card['id']]['due_now'])
            moment=result['next_review']
        with patch('h3chat.study.time.time',return_value=moment):
            result=study.progress(self.app,chat,value['id'],{'card_id':card['id'],'remembered':False})['items'][card['id']]
            self.assertEqual(result['next_review'],moment+600);self.assertEqual(result['streak'],0);self.assertEqual(result['attempts'],7)
        with patch('h3chat.study.time.time',return_value=moment+600):
            result=study.progress(self.app,chat,value['id'],{'card_id':card['id'],'remembered':True})['items'][card['id']]
            self.assertEqual(result['next_review'],moment+600+86400)

    def test_schedules_follow_content_revisions_and_are_chat_scoped(self):
        chat,job=self.launch(count=1);self.execute(job)
        value=self.app.store.canvas_history.get(chat);deck=study.decode(value['content']);card=deck['items'][0]
        original=study.progress(self.app,chat,value['id'],{'card_id':card['id'],'remembered':True})
        updated=copy.deepcopy(deck);updated['items'][0]['answer']+=' Testo modificato.'
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':study.encode(updated),'media':[]},edit_id=value['id'],editable=True)
        self.assertEqual(study.progress(self.app,chat,saved['id'])['items'],{})
        self.assertEqual(study.progress(self.app,chat,value['id']),original)
        other=self.app.store.create_chat('Altro studio')['id']
        copy_value=self.app.store.canvas_history.save(other,{'title':deck['title'],'content':study.encode(deck),'media':[]},editable=True)
        self.assertEqual(study.progress(self.app,other,copy_value['id'])['items'],{})

    def test_existing_reviews_without_schedule_remain_visible(self):
        chat,job=self.launch(count=1);self.execute(job)
        value=self.app.store.canvas_history.get(chat);card=study.decode(value['content'])['items'][0]
        study.progress(self.app,chat,value['id'],{'card_id':card['id'],'remembered':True})
        self.app.store.execute('DELETE FROM study_schedule_v1')
        result=study.progress(self.app,chat,value['id'])['items'][card['id']]
        self.assertEqual(result['attempts'],1);self.assertTrue(result['due_now']);self.assertIsNone(result['next_review'])
