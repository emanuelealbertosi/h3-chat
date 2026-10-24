import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from h3chat.downloads import Cancelled
from h3chat.service import Service
from h3chat.slide_resume import enqueue
from h3chat.slides import PREFIX, encode

ROOT = Path(__file__).resolve().parents[1]


class SlideResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Service(ROOT, self.temp.name, start_worker=False)
        self.addCleanup(self.app.close)
        self.model = {'id': 'fixture-chat', 'name': 'Current model', 'capabilities': ['chat'], 'files': [], 'vision': {'enabled': False}}
        self.chat = self.app.store.create_chat()['id']

    def saved(self, engine='llm'):
        deck = {'version': 1, 'engine': engine, 'format': '16:9', 'title': 'Lezione',
                'references': [{'id': 'R1', 'label': 'Libro · pagina 4'}], 'pages': [
                    {'title': 'Pronta', 'status': 'ready', 'html': '<main><h1>Pronta</h1><p>Conservare [R1]</p></main>', 'notes': 'Nota originale', 'sources': ['R1']},
                    {'title': 'Da finire', 'status': 'interrupted', 'html': '<main><h1>Bozza</h1></main>', 'notes': 'Spiegazione già preparata', 'editorial': {'content': 'Esempio originale'}, 'sources': []},
                    {'title': 'Ultima', 'status': 'pending', 'html': '', 'notes': '', 'sources': []}]}
        if engine == 'deterministic':
            for page in deck['pages']:
                page.pop('html', None)
                page['nodes'] = [self.node(page['title'])] if page['status'] == 'ready' else []
        settings = self.app.store.settings()
        ident = self.app.store.enqueue(self.chat, 'Richiesta originale', [], settings, True)
        job = self.app.store.one('SELECT * FROM jobs WHERE id=?', (ident,))
        self.app.store.update_answer(job, 'Presentazione interrotta', 'cancelled', meta={
            'canvas': True, 'artifact': {'title': deck['title'], 'content': encode(deck), 'media': []},
            'rag_sources': [{'citation': 'R1', 'name': 'Libro', 'location': 'pagina 4', 'text': 'Contenuto verificato della fonte'}]})
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (ident,))
        return self.app.store.canvas_history.get(self.chat), deck

    @staticmethod
    def node(text):
        return {'id': 'n1', 'parent': 'root', 'kind': 'heading', 'text': text, 'asset_id': '', 'language': '',
                'style': {'flow': 'stack', 'columns': [1], 'surface': 'accent', 'gap': 12}}

    def queue(self, artifact):
        with patch.object(self.app.engine, 'require_model', return_value=self.model):
            response = enqueue(self.app, self.chat, {'artifact_id': artifact['id']})
        return self.app.store.one('SELECT * FROM jobs WHERE id=?', (response['job_id'],))

    def execute(self, job, completion, cancel=None):
        with patch.object(self.app.engine, 'require_model', return_value=self.model), \
             patch.object(self.app.engine, 'prepare') as prepare, \
             patch.object(self.app.engine, 'start_llama') as start, \
             patch.object(self.app.engine, 'completion', side_effect=completion) as complete:
            self.app.execute_job(job, cancel or threading.Event())
        return self.app.store.messages(self.chat)[-1], prepare, start, complete

    def result(self, answer):
        return json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])

    def test_saved_phase_timeout_is_used_by_resume_and_page_revision(self):
        saved,deck=self.saved();deck['llm_timeout']=6000
        saved=self.app.store.canvas_history.save(self.chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        job=self.queue(saved);seen=[]
        def complete(messages,settings,cancel,**kw):
            seen.append(settings['llm_timeout'])
            return '<main style="color:blue"><h1>Pagina completata</h1><p>Testo aggiornato.</p></main>','stop'
        answer,_,start,_=self.execute(job,complete)
        self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(seen,[6000,6000]);self.assertEqual(start.call_args.args[1]['llm_timeout'],6000)
        self.assertEqual(self.result(answer)['llm_timeout'],6000)

    def test_only_missing_pages_change_and_sources_history_survive(self):
        saved, original = self.saved()
        job = self.queue(saved)
        calls = []
        def complete(messages, settings, cancel, **kw):
            calls.append(copy.deepcopy(messages))
            self.assertIn('Contenuto verificato della fonte', messages[1]['content'])
            self.assertIn('RICHIESTA ATTUALE', messages[-1]['content'])
            kw['on_text']('<style>h1{color:blue}</style><main><h1>Nuova pagina')
            return f'<style>h1{{color:blue}}</style><main><h1>Pagina completa {len(calls)}</h1><p>Fonte [R1]</p></main>', 'stop'
        answer, prepare, start, completion = self.execute(job, complete)
        self.assertEqual(answer['status'], 'done', answer['meta'].get('error'))
        result = self.result(answer)
        self.assertEqual(result['pages'][0], original['pages'][0])
        self.assertTrue(all(p['status'] == 'ready' for p in result['pages']))
        self.assertEqual(result['pages'][1]['editorial'], original['pages'][1]['editorial'])
        self.assertEqual(completion.call_count, 2)
        prepare.assert_called_once(); start.assert_called_once()
        self.assertEqual(self.app.store.canvas_history.get(self.chat, saved['id'])['content'], encode(original))
        self.assertEqual(answer['meta']['slide_resume']['completed'], 2)
        self.assertEqual(answer['meta']['model'], 'Current model')
        self.assertEqual(answer['meta']['rag_sources'][0]['citation'], 'R1')

    def test_second_resume_keeps_completed_page_and_reuses_interrupted_edit(self):
        saved, original = self.saved()
        original['pages'][2]['revision_prompt'] = 'Sposta il titolo sopra la figura e usa il viola'
        saved = self.app.store.canvas_history.save(self.chat, {'title': original['title'], 'content': encode(original), 'media': []})
        job = self.queue(saved); calls = []
        def complete(messages, settings, cancel, **kw):
            calls.append(messages[-1]['content'])
            if len(calls) == 2:
                kw['on_text']('<main><h1>Titolo interrotto')
                raise Cancelled()
            return '<main style="color:blue"><h1>Slide finita</h1></main>', 'stop'
        answer, _, _, _ = self.execute(job, complete)
        self.assertEqual(answer['status'], 'cancelled')
        partial = self.result(answer)
        self.assertEqual(partial['pages'][0], original['pages'][0])
        self.assertEqual(partial['pages'][1]['status'], 'ready')
        self.assertEqual(partial['pages'][2]['status'], 'interrupted')
        self.assertIn(original['pages'][2]['revision_prompt'], calls[-1])
        job = self.queue(self.app.store.canvas_history.get(self.chat))
        def finish(messages, settings, cancel, **kw):
            self.assertIn(original['pages'][2]['revision_prompt'], messages[-1]['content'])
            return '<main style="color:purple"><h1>Titolo corretto</h1></main>', 'stop'
        answer, _, _, complete = self.execute(job, finish)
        self.assertEqual(answer['status'], 'done', answer['meta'].get('error'))
        result = self.result(answer)
        self.assertEqual(result['pages'][:2], partial['pages'][:2])
        self.assertEqual(complete.call_count, 1)
        self.assertNotIn('revision_prompt', result['pages'][2])

    def test_deterministic_deck_resumes_without_replanning(self):
        saved, original = self.saved('deterministic'); job = self.queue(saved)
        def complete(messages, settings, cancel, **kw):
            self.assertIn('Sequenza:', messages[-1]['content'])
            page = {'nodes': [self.node('Contenuto completato')], 'notes': 'Nota completa', 'sources': ['R1']}
            kw['on_text'](json.dumps(page))
            return json.dumps(page), 'stop'
        answer, prepare, _, complete = self.execute(job, complete)
        self.assertEqual(answer['status'], 'done', answer['meta'].get('error'))
        result = self.result(answer)
        self.assertEqual(result['pages'][0], original['pages'][0])
        self.assertTrue(all(p['status'] == 'ready' for p in result['pages']))
        self.assertEqual(complete.call_count, 2); prepare.assert_called_once()

    def test_completed_html_from_interrupted_stream_can_be_accepted_without_edit(self):
        saved, original = self.saved()
        original['pages'] = original['pages'][:2]
        original['pages'][1]['html'] = '<main style="color:blue"><h1>Pagina già ricevuta interamente</h1></main>'
        saved = self.app.store.canvas_history.save(self.chat, {'title': original['title'], 'content': encode(original), 'media': []})
        job = self.queue(saved)
        answer, _, _, complete = self.execute(job, lambda *a, **kw: (original['pages'][1]['html'], 'stop'))
        self.assertEqual(answer['status'], 'done', answer['meta'].get('error'))
        self.assertEqual(complete.call_count, 1)
        self.assertEqual(self.result(answer)['pages'][1]['status'], 'ready')

    def test_stop_at_structured_completion_keeps_page_interrupted(self):
        saved, _ = self.saved('deterministic'); job = self.queue(saved)
        cancel = threading.Event()
        def complete(*args, **kw):
            cancel.set()
            return json.dumps({'nodes': [self.node('Risposta tardiva')], 'notes': '', 'sources': []}), 'stop'
        answer, _, _, _ = self.execute(job, complete, cancel)
        self.assertEqual(answer['status'], 'cancelled')
        result = self.result(answer)
        self.assertEqual(result['pages'][1]['status'], 'interrupted')
        self.assertEqual(result['pages'][2]['status'], 'pending')

    def test_rejects_foreign_complete_decks_and_duplicate_submission(self):
        saved, original = self.saved()
        other = self.app.store.create_chat()['id']
        with self.assertRaises(ValueError): enqueue(self.app, other, {'artifact_id': saved['id']})
        for p in original['pages']:
            p.update(status='ready', html='<main><h1>Completa</h1></main>')
        complete = self.app.store.canvas_history.save(self.chat, {'title': original['title'], 'content': encode(original), 'media': []})
        with self.assertRaisesRegex(ValueError, 'già complete'):
            enqueue(self.app, self.chat, {'artifact_id': complete['id']})
        self.queue(saved)
        with patch.object(self.app.engine, 'require_model', return_value=self.model), self.assertRaisesRegex(ValueError, 'richiesta attiva'):
            enqueue(self.app, self.chat, {'artifact_id': saved['id']})


if __name__ == '__main__': unittest.main()
