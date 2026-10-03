import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from app import Handler, ThreadingHTTPServer
from h3chat.service import Service
from h3chat.store import DEFAULTS, Store

ROOT = Path(__file__).resolve().parents[1]


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.chat = self.store.create_chat()['id']
        self.history = self.store.canvas_history

    def artifact(self, content='Original', **kwargs):
        return self.history.save(self.chat, {'title':'Documento', 'content':content, 'media':[]}, **kwargs)

    def test_streaming_keeps_one_entry_and_preserves_previous_output(self):
        first = self.artifact(key='job:first')
        for text in ('A', 'AB', 'ABC'):
            second = self.artifact(text, key='job:second')
        items = self.history.listing(self.chat)['items']
        self.assertEqual(len(items), 2)
        self.assertEqual(self.history.get(self.chat, first['id'])['content'], 'Original')
        self.assertEqual(self.history.get(self.chat, second['id'])['content'], 'ABC')

    def test_browsing_is_read_only_and_restore_changes_the_next_request_snapshot(self):
        first = self.artifact(key='job:first')
        latest = self.artifact('Latest', key='job:second')
        self.history.get(self.chat, first['id'])
        self.assertEqual(self.history.get(self.chat)['id'], latest['id'])
        self.history.restore(self.chat, first['id'])
        job = self.store.enqueue(self.chat, 'Modifica questo documento', [], DEFAULTS, True)
        payload = json.loads(self.store.one('SELECT payload FROM jobs WHERE id=?', (job,))['payload'])
        self.assertEqual(payload['canvas_snapshot']['content'], 'Original')
        self.assertEqual(len(self.history.listing(self.chat)['items']), 2)

    def test_editing_generated_output_preserves_original_and_updates_one_working_copy(self):
        first = self.artifact(key='job:first', message_id='answer')
        edited = self.artifact('Edited', edit_id=first['id'])
        again = self.artifact('Edited again', edit_id=edited['id'])
        self.assertNotEqual(first['id'], edited['id'])
        self.assertEqual(edited['id'], again['id'])
        self.assertEqual(again['message_id'], 'answer')
        self.assertEqual(self.history.get(self.chat, first['id'])['content'], 'Original')
        self.assertEqual(len(self.history.listing(self.chat)['items']), 2)
        self.assertEqual(self.artifact('Edited again', edit_id=again['id'])['id'], again['id'])

    def test_previous_message_artifacts_and_legacy_canvas_are_imported_once(self):
        self.store.execute('INSERT INTO canvases VALUES (?,?,?,?,?)', (self.chat, 'Old draft', 'Manual work', '[]', 3))
        for i, meta, media, status in [
            (1, {'artifact':{'title':'Diagramma', 'content':'```mermaid\ngraph LR; A-->B\n```', 'media':[]}}, [], 'done'),
            (2, {'intent':'video'}, [{'id':'a'*32, 'path':'outputs/old.mp4', 'name':'old.mp4', 'mime':'video/mp4'}], 'done'),
            (3, {}, [], 'done'),
            (4, {'artifact':{'title':'Interrotto', 'content':'Recovered source', 'media':[]}}, [], 'interrupted'),
        ]:
            self.store.execute("INSERT INTO messages(id,chat_id,role,content,media,status,created,meta) VALUES (?,?,'assistant',?,?,?,?,?)",
                (str(i), self.chat, 'Answer', json.dumps(media), status, i, json.dumps(meta)))
        items = self.history.listing(self.chat)['items']
        self.assertEqual({i['title'] for i in items}, {'Diagramma','Video','Old draft','Interrotto'})
        self.assertEqual(self.history.get(self.chat)['content'], 'Manual work')
        self.assertEqual(len(self.history.listing(self.chat)['items']), 4)
        self.assertEqual(self.history.get(self.chat, next(x['id'] for x in items if x['title']=='Video'))['media'][0]['name'], 'old.mp4')

    def test_terminal_output_outside_canvas_is_available_without_replacing_current(self):
        first = self.artifact()
        job_id = self.store.enqueue(self.chat, 'Create', [], DEFAULTS)
        job = self.store.one('SELECT * FROM jobs WHERE id=?', (job_id,))
        self.store.update_answer(job, 'Created', 'done', [{'id':'a'*32, 'name':'result.png', 'path':'outputs/result.png', 'mime':'image/png'}], {'intent':'create'})
        items = self.history.listing(self.chat)['items']
        self.assertEqual(len(items), 2)
        self.assertEqual(self.history.get(self.chat)['id'], first['id'])
        self.assertEqual(items[-1]['message_id'], job['message_id'])

    def test_failed_artifact_and_regeneration_remain_recoverable(self):
        job_id = self.store.enqueue(self.chat, 'Manim', [], DEFAULTS, True)
        job = self.store.one('SELECT * FROM jobs WHERE id=?', (job_id,))
        meta = {'canvas':True, 'artifact':{'title':'Scene', 'content':'Python source', 'media':[]}}
        self.store.update_answer(job, 'Failed', 'failed', [], meta)
        self.store.execute("UPDATE jobs SET status='failed' WHERE id=?", (job_id,))
        first = self.history.get(self.chat)
        retry_id = self.store.regenerate(self.chat)
        retry = self.store.one('SELECT * FROM jobs WHERE id=?', (retry_id,))
        meta['artifact']['content'] = 'Fixed source'
        self.store.update_answer(retry, 'Ready', 'done', [], meta)
        self.assertEqual(len(self.history.listing(self.chat)['items']), 2)
        self.assertEqual(self.history.get(self.chat, first['id'])['content'], 'Python source')

    def test_old_unmigrated_answer_is_preserved_before_regeneration(self):
        job_id = self.store.enqueue(self.chat, 'Create', [], DEFAULTS)
        job = self.store.one('SELECT * FROM jobs WHERE id=?', (job_id,))
        self.store.execute("UPDATE messages SET status='done',meta=? WHERE id=?", (json.dumps({'artifact':{'title':'Legacy', 'content':'Before', 'media':[]}}), job['message_id']))
        self.store.execute("UPDATE jobs SET status='done' WHERE id=?", (job_id,))
        self.store.regenerate(self.chat)
        self.assertEqual(self.history.get(self.chat, self.history.listing(self.chat)['items'][0]['id'])['content'], 'Before')

    def test_isolation_deletion_and_restart(self):
        first = self.artifact()
        other = self.store.create_chat()['id']
        for operation in (lambda:self.history.get(other, first['id']), lambda:self.history.restore(other, first['id']),
                          lambda:self.history.save(other, first, edit_id=first['id'])):
            with self.assertRaisesRegex(ValueError, 'questa chat'):
                operation()
        restarted = Store(self.temp.name)
        self.assertEqual(restarted.canvas_history.get(self.chat)['id'], first['id'])
        self.store.execute('DELETE FROM chats WHERE id=?', (self.chat,))
        self.assertEqual(self.store.all('SELECT * FROM canvas_artifacts'), [])
        self.assertEqual(self.store.all('SELECT * FROM canvas_heads'), [])

    def test_read_during_generation_is_allowed_but_restoring_or_editing_is_blocked(self):
        first = self.artifact()
        self.store.enqueue(self.chat, 'Write', [], DEFAULTS, True)
        self.assertEqual(self.history.get(self.chat, first['id'])['content'], 'Original')
        self.assertEqual(len(self.history.listing(self.chat)['items']), 1)
        with self.assertRaisesRegex(ValueError, 'motore'):
            self.history.restore(self.chat, first['id'])
        with self.assertRaisesRegex(ValueError, 'motore'):
            self.artifact('Blocked', edit_id=first['id'], editable=True)


class HistoryApiTests(unittest.TestCase):
    def test_history_routes_media_from_old_artifact_and_session_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Service(ROOT, Path(folder), start_worker=False)
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.app = app
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            def request(path, body=None, method='GET', token=None):
                req = urllib.request.Request(base + path, method=method,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json', 'X-H3-Token':app.token if token is None else token})
                with urllib.request.urlopen(req) as response:
                    return json.load(response)
            try:
                chat = app.store.create_chat()['id']
                image = {'id':'a'*32, 'name':'old.png', 'path':'outputs/old.png', 'mime':'image/png'}
                old = app.store.canvas_history.save(chat, {'title':'Old', 'content':'', 'media':[image]}, key='job:first')
                app.store.canvas_history.save(chat, {'title':'New', 'content':'New', 'media':[]}, key='job:second')
                items = request(f'/api/canvas/{chat}/history')['items']
                self.assertEqual(len(items), 2)
                self.assertEqual(request(f'/api/canvas/{chat}/history/{old["id"]}')['media'], [image])
                edited = request(f'/api/canvas/{chat}', old | {'title':'Edited'}, 'PUT')
                self.assertNotEqual(edited['id'], old['id'])
                self.assertEqual(edited['media'], [image])
                path = f'/api/canvas/{chat}/history/{old["id"]}/restore'
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    request(path, {}, 'POST', token='')
                self.assertEqual(cm.exception.code, 403)
                request(path, {}, 'POST')
                self.assertEqual(request(f'/api/canvas/{chat}')['id'], old['id'])
                outputs = Path(folder) / 'outputs'; outputs.mkdir(exist_ok=True)
                (outputs / 'manim-render.log').write_text('Synthetic renderer diagnostics')
                with urllib.request.urlopen(base + '/media/outputs/manim-render.log') as response:
                    self.assertEqual(response.read(), b'Synthetic renderer diagnostics')
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    urllib.request.urlopen(base + '/media/logs/private.log')
                self.assertEqual(cm.exception.code, 403)
            finally:
                server.shutdown(); server.server_close(); thread.join(); app.close()


if __name__ == '__main__':
    unittest.main()
