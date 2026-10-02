import json
import tempfile
import unittest
from pathlib import Path
from h3chat.store import Store, DEFAULTS


class RegenerateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.chat = self.store.create_chat()['id']

    def test_replays_snapshot_without_duplicate_user_or_own_answer_in_history(self):
        s = self.store
        media = [{'id':'source','mime':'image/png','path':'uploads/source.png'}]
        settings = DEFAULTS | {'_video':True,'_assistant':False,'think_level':'high',
            'video_overrides':{'hybrid':{'steps':12,'seed':-1}}}
        loras = [{'id':'lora','name':'Style','weight':.7,'model_id':'img','model_name':'Image'}]
        s.execute('INSERT INTO canvases VALUES (?,?,?,?,?)', (self.chat,'Original','Before','[]',1))
        first = s.enqueue(self.chat,'Animate image 1',media,settings,True,loras)
        old = s.one('SELECT * FROM jobs WHERE id=?',(first,))
        s.update_answer(old,'Previous video','done',[{'id':'output'}],{'canvas':True})
        s.execute("UPDATE jobs SET status='done' WHERE id=?",(first,))
        s.save_settings({'think_level':'off'})
        s.execute("UPDATE canvases SET content='Later' WHERE chat_id=?",(self.chat,))
        for _ in range(2):
            again = s.regenerate(self.chat)
            job = s.one('SELECT * FROM jobs WHERE id=?',(again,))
            self.assertNotEqual(again,first)
            self.assertEqual(job['payload'],old['payload'])
            self.assertEqual(job['message_id'],old['message_id'])
            messages = s.chat(self.chat)['messages']
            self.assertEqual(len(messages),2)
            self.assertEqual(messages[-1]['status'],'queued')
            self.assertEqual((messages[-1]['content'],messages[-1]['media'],messages[-1]['meta']),('',[],{}))
            payload = json.loads(job['payload'])
            history = s.messages(self.chat,payload['until'])
            self.assertEqual([m['role'] for m in history],['user'])
            self.assertEqual(payload['canvas_snapshot']['content'],'Before')
            s.execute("UPDATE jobs SET status='failed' WHERE id=?",(again,))

    def test_busy_archived_empty_and_missing_chat_are_rejected(self):
        s = self.store
        with self.assertRaisesRegex(ValueError,'prima'):s.regenerate(self.chat)
        with self.assertRaisesRegex(ValueError,'non trovata'):s.regenerate('missing')
        first = s.enqueue(self.chat,'Hello',[],DEFAULTS)
        with self.assertRaisesRegex(ValueError,'Attendi'):s.regenerate(self.chat)
        s.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(first,))
        s.execute('UPDATE chats SET archived=1 WHERE id=?',(self.chat,))
        with self.assertRaisesRegex(ValueError,'archivio'):s.regenerate(self.chat)

    def test_latest_prompt_is_chosen_with_prior_context_and_chat_isolation(self):
        s = self.store
        first = s.enqueue(self.chat,'First',[],DEFAULTS)
        s.execute("UPDATE jobs SET status='done' WHERE id=?",(first,))
        s.update_answer(s.one('SELECT * FROM jobs WHERE id=?',(first,)),'First answer','done')
        second = s.enqueue(self.chat,'Second',[],DEFAULTS)
        s.execute("UPDATE jobs SET status='interrupted' WHERE id=?",(second,))
        other = s.create_chat()['id']
        s.enqueue(other,'Unrelated',[],DEFAULTS)
        again = s.regenerate(self.chat)
        payload = json.loads(s.one('SELECT payload FROM jobs WHERE id=?',(again,))['payload'])
        self.assertEqual(payload['prompt'],'Second')
        self.assertEqual([m['content'] for m in s.messages(self.chat,payload['until'])],['First','First answer','Second'])


if __name__ == '__main__':unittest.main()
