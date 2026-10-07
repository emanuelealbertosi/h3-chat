"""Artifact catalogues must not become an oversized implicit Vision request."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.engine import Engine
from h3chat.store import DEFAULTS

ROOT=Path(__file__).resolve().parents[1]


class ReferenceContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.engine=Engine(ROOT,self.temp.name,{})
        self.model={'id':'fixture','name':'Fixture','capabilities':['chat'],'files':[],
                    'vision':{'enabled':True,'max_refs':4}}
        folder=Path(self.temp.name)/'uploads';folder.mkdir()
        for i in range(12):(folder/f'{i}.png').write_bytes(b'synthetic picture')
        self.images=[{'id':str(i),'name':f'Figura {i}','mime':'image/png','path':f'uploads/{i}.png'} for i in range(12)]

    def message(self,role='user',seq=1,media=None,content='Fonte originale [R1]'):
        return {'role':role,'seq':seq,'status':'done','media':media or [],'content':content}

    def parts(self,messages):
        return [p for m in messages if isinstance(m['content'],list) for p in m['content'] if p.get('type')=='image_url']

    def test_previous_twelve_image_deck_preserves_facts_without_reading_or_truncating_gallery(self):
        previous=self.message('assistant',0,self.images)
        previous['meta']={'artifact':{'content':'Deck','media':self.images}}
        history=[previous,self.message(seq=1,content='Crea Manim con voce [R2]')]
        with patch('pathlib.Path.read_bytes',side_effect=AssertionError('Unselected gallery must not be read')):
            messages=self.engine.chat_messages(history,self.model,DEFAULTS)
        self.assertEqual(self.parts(messages),[])
        self.assertIn('Fonte originale [R1]',messages[1]['content'])
        self.assertIn('Figura 11',messages[1]['content'])
        self.assertIn('non sono state inviate a Vision',messages[1]['content'])
        self.assertEqual(history[0]['media'],self.images)
        self.assertEqual(messages[-1]['content'],'Crea Manim con voce [R2]')

    def test_current_selected_or_rag_images_win_over_previous_large_gallery(self):
        for count in (1,4):
            history=[self.message('assistant',0,self.images),self.message(seq=1,media=self.images[:count])]
            messages=self.engine.chat_messages(history,self.model,DEFAULTS)
            self.assertEqual(len(self.parts(messages)),count)
            self.assertIn('[R1]',messages[-1]['content'][-1]['text'])

    def test_real_current_upload_limit_is_enforced_and_no_missing_max_refs_key(self):
        with self.assertRaisesRegex(ValueError,'fino a 4 riferimenti'):
            self.engine.chat_messages([self.message(media=self.images[:5])],self.model,DEFAULTS)

    def test_configured_native_limit_can_exceed_catalogue_default_and_reduce_it(self):
        self.assertEqual(len(self.parts(self.engine.chat_messages(
            [self.message(media=self.images[:6])],self.model,DEFAULTS|{'vision_max_refs':6}))),6)
        with self.assertRaisesRegex(ValueError,'fino a 2 riferimenti'):
            self.engine.chat_messages([self.message(media=self.images[:3])],self.model,DEFAULTS|{'vision_max_refs':2})

    def test_provider_capacity_remains_authoritative(self):
        model=self.model|{'api':True,'max_refs':2}
        with self.assertRaisesRegex(ValueError,'fino a 2 riferimenti'):
            self.engine.chat_messages([self.message(media=self.images[:3])],model,DEFAULTS|{'vision_max_refs':6})

    def test_single_generated_reference_still_reaches_vision_after_nonimage_files(self):
        pdf={'id':'pdf','name':'Libro.pdf','path':'not-read.pdf','mime':'application/pdf'}
        history=[self.message('assistant',0,self.images[:1]),self.message(seq=1,media=[pdf])]
        messages=self.engine.chat_messages(history,self.model,DEFAULTS)
        self.assertEqual(len(self.parts(messages)),1)
        self.assertTrue(self.parts(messages)[0]['image_url']['url'].startswith('data:image/png;'))

    def test_oversized_canvas_snapshot_is_catalogue_and_nonimages_do_not_require_vision(self):
        history=[self.message(seq=-1,media=self.images),self.message(seq=1)]
        self.assertEqual(self.parts(self.engine.chat_messages(history,self.model,DEFAULTS)),[])
        history=[self.message(media=[{'mime':'application/pdf','path':'unread.pdf'}])]
        messages=self.engine.chat_messages(history,self.model,DEFAULTS|{'vision_enabled':False})
        self.assertEqual(self.parts(messages),[])


if __name__=='__main__':unittest.main()
