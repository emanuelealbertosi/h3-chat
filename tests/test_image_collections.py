import base64,hashlib,json,threading,unittest,zipfile
from unittest.mock import patch
import test_visual_models as fixture
from h3chat import image_collections as lots
from test_image_batch import PNG

class CollectionTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown
    def image(self,name):return self.app.upload({'name':name+'.png','data':base64.b64encode(PNG).decode()})
    def lot(self):
        images=[self.image('rosso'),self.image('blu')]
        return lots.create(self.app,{'name':'Esempi','images':[{'id':m['id'],'prompt':'Prompt di generazione'} for m in images]})
    def test_saved_lot_export_manifest_checksums_and_no_original_mutation(self):
        value=self.lot();before=[(self.app.data/i['media']['path']).read_bytes() for i in value['images']]
        result=lots.export(self.app,value['id'])
        with zipfile.ZipFile(self.app.data/result['url'].lstrip('/')) as archive:
            manifest=json.loads(archive.read('manifest.json'));self.assertEqual(manifest['name'],'Esempi')
            for item in manifest['images']:
                raw=archive.read(item['file']);self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256']);self.assertNotIn('path',item)
                self.assertEqual(item['prompt'],'Prompt di generazione');self.assertEqual(item['caption'],'')
        self.assertEqual(before,[(self.app.data/i['media']['path']).read_bytes() for i in value['images']])
        self.assertEqual(lots.listing(self.app)['items'][0]['available'],2)
    def test_captions_distinct_from_prompts_and_text_rag_retrieves_figure(self):
        value=self.lot();image=value['images'][0]['media'];lots.update(self.app,value['id'],{'image_id':image['id'],'caption':'Circuito elettronico con porta AND rossa'})
        saved=lots.get(self.app,value['id']);self.assertEqual(saved['images'][0]['prompt'],'Prompt di generazione');self.assertEqual(saved['captioned'],1)
        with self.assertRaisesRegex(ValueError,'Catalogazione incompleta'):lots.add_to_rag(self.app,value['id'],{'project_id':self.app.knowledge.save({'name':'Fisica'})['id']})
        lots.update(self.app,value['id'],{'image_id':value['images'][1]['media']['id'],'caption':'Mare e cielo blu'})
        project=self.app.knowledge.save({'name':'Elettronica'})['id']
        with patch.object(self.app.knowledge,'refresh',return_value={'status':'indexing'}):lots.add_to_rag(self.app,value['id'],{'project_id':project})
        settings=self.app.store.settings()|{'rag_embedding_model':'','rag_visual':False}
        self.app.knowledge.index(project,settings,threading.Event(),lambda s:None)
        chunks=self.app.store.all('SELECT * FROM rag_chunks');self.assertEqual(len(chunks),2);self.assertTrue(all(c['image_path'] for c in chunks))
        found,_=self.app.knowledge.retrieve(project,'Circuito elettronico porta AND',settings,threading.Event(),lambda s:None)
        self.assertTrue(any('porta AND' in r['text'] for r in found))
    def test_changed_pixels_invalidate_caption_and_bad_ids_rejected(self):
        value=self.lot();image=value['images'][0]['media'];lots.update(self.app,value['id'],{'image_id':image['id'],'caption':'Descrizione'})
        path=self.app.data/image['path'];self.assertEqual(lots.caption_for_path(self.app.data,path),'Descrizione');path.write_bytes(b'changed');self.assertEqual(lots.caption_for_path(self.app.data,path),'')
        with self.assertRaises(ValueError):lots.get(self.app,'../escape')
        with self.assertRaises(ValueError):lots.create(self.app,{'images':[1]})
        with self.assertRaises(ValueError):lots.get(self.app,'f'*32)
    def test_imported_backgrounds_keep_options_and_are_reusable(self):
        m=self.image('bordo');value=lots.create(self.app,{'kind':'backgrounds','name':'Cornici importate','options':{'name':'Cornici importate','margin':6},'images':[{'id':m['id'],'caption':'Bordo con circuiti'}]})
        from h3chat.slide_backgrounds import listing
        saved=listing(self.app)['items'][0];self.assertEqual(saved['id'],value['id']);self.assertEqual(saved['options']['margin'],6);self.assertEqual(saved['images'][0]['caption'],'Bordo con circuiti')
    def test_caption_job_uses_vision_and_preserves_completed_descriptions(self):
        value=self.lot();chat=self.app.store.create_chat()['id'];model={'id':'vision-test','name':'Vision test','vision':{'enabled':True}}
        with patch.object(self.app.engine,'require_model',return_value=model):ticket=lots.enqueue_caption(self.app,value['id'],{'chat_id':chat})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));settings=json.loads(job['payload'])['settings']
        with patch.object(self.app.engine,'require_model',return_value=model),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch('h3chat.slide_vision.describe',side_effect=lambda a,images,*args,**kwargs:{images[0]['id']:'Descrizione Vision'}):
            lots.caption_job(self.app,job,settings,threading.Event(),lambda s:None,self.app.data/'test.log')
        result=lots.get(self.app,value['id']);self.assertEqual(result['captioned'],2);self.assertTrue(all(i['caption_source']=='vision' for i in result['images']))

if __name__=='__main__':unittest.main()
