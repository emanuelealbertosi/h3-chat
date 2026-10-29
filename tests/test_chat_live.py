import unittest
import test_visual_models as fixture
from h3chat.chat_live import read

class LiveChat(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown
    def test_live_answer_is_scoped_to_its_chat_and_plain_text_generation(self):
        chat=self.app.store.create_chat()['id'];other=self.app.store.create_chat()['id']
        ticket=self.app.send(chat,{'prompt':'Saluta','assistant':False});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
        self.app.store.update_answer(job,'Testo già ricevuto 😀',meta={'intent':'chat'})
        result=read(self.app,chat,job['message_id']);self.assertEqual(result['content'],'Testo già ricevuto 😀');self.assertEqual(set(result),{'id','content','status'})
        with self.assertRaises(ValueError):read(self.app,other,job['message_id'])
        self.app.store.update_answer(job,'Canvas',meta={'intent':'chat','canvas':True})
        with self.assertRaises(ValueError):read(self.app,chat,job['message_id'])
        with self.assertRaises(ValueError):read(self.app,'../data',job['message_id'])
