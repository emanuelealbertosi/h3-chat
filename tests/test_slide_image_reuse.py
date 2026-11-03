import base64,copy,json,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from h3chat.slide_image_reuse import resolve
from h3chat.slide_generation_images import create
from h3chat.request_draft import load
from test_slide_images import ImageTests,png


class SlideReuseTests(ImageTests):
    def source(self):
        settings=self.app.store.settings()|{'_lab':'slides','_slides':{'generate_images':True}}
        ident=self.app.store.enqueue(self.chat['id'],'Originale',[],settings)
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        meta={'slide_generated_images':[self.media],'slide_image_plan':[{'slide':1,'asset_id':self.media['id'],'description':'Un faro blu','aspect':'1:1','width':2,'height':2}]}
        self.app.store.update_answer(job,'Parziale',status='cancelled',meta=meta)
        return job

    def test_partial_results_offer_reuse_but_other_chat_and_missing_files_do_not(self):
        job=self.source();offer=load(self.app,self.chat['id'],job['message_id'])['slide_image_reuse']
        self.assertEqual(offer,{'job_id':job['id'],'count':1})
        with self.assertRaises(ValueError):resolve(self.app,self.app.store.create_chat()['id'],job['id'])
        (self.app.data/self.media['path']).unlink()
        self.assertEqual(resolve(self.app,self.chat['id'],job['id']),[])
        self.assertIsNone(load(self.app,self.chat['id'],job['message_id'])['slide_image_reuse'])

    def render(self,job,rows):
        engine=Mock();self.app.engine=engine
        engine.require_model.return_value={'id':'image','name':'Fixture','architecture':'anima'}
        engine.completion.return_value=(json.dumps({'images':rows}),'stop')
        engine.generate.side_effect=lambda *a:dict(self.media,id='f'*32)
        settings=self.app.store.settings()|{'_slides':{'image_model':'image','generate_images':True,'reuse_images_from':job['id']}}
        outline={'title':'Nuova scaletta','slides':[{'title':'Faro','purpose':'Esempio'},{'title':'Mare','purpose':'Nuovo contenuto'}]}
        meta={};assets,_=create(self.app,job,outline,[],settings,{},threading.Event(),Mock(),Path('fixture.log'),meta)
        return engine,meta,assets

    def test_mixed_reuse_and_new_generation_preserve_id_and_checkpoint(self):
        job=self.source();engine,meta,assets=self.render(job,[{'slide':2,'prompt':'blue lighthouse','description':'Faro','aspect':'1:1','reuse_asset_id':self.media['id']},
            {'slide':1,'prompt':'open sea','description':'Mare','aspect':'16:9','reuse_asset_id':''}])
        engine.generate.assert_called_once();self.assertEqual([m['id'] for m in assets],[self.media['id'],'f'*32])
        self.assertEqual((meta['slide_images_reused'],meta['slide_images_created']),(1,1))
        self.assertEqual(meta['slide_image_plan'][0]['slide'],2)
        self.assertIn(self.media['id'],engine.completion.call_args.args[0][-1]['content'])

    def test_all_reused_skips_model_stop_start_and_generation(self):
        job=self.source();engine,meta,_=self.render(job,[{'slide':1,'prompt':'blue lighthouse','description':'Faro','aspect':'1:1','reuse_asset_id':self.media['id']}])
        engine.generate.assert_not_called();engine.stop.assert_not_called();engine.start_llama.assert_not_called()
        self.assertEqual(meta['slide_images_reused'],1)

    def test_unlisted_reuse_fails_before_loading_image_model(self):
        job=self.source()
        with self.assertRaisesRegex(ValueError,'non autorizzata'):self.render(job,[{'slide':1,'prompt':'blue lighthouse','description':'Faro','aspect':'1:1','reuse_asset_id':'b'*32}])
        self.app.engine.generate.assert_not_called();self.app.engine.stop.assert_not_called()

    def test_unused_cache_images_remain_available_alongside_new_images(self):
        job=self.source();_,meta,_=self.render(job,[{'slide':1,'prompt':'open sea','description':'Mare','aspect':'16:9'}])
        self.app.store.update_answer(job,'Nuove figure',status='done',meta=meta)
        self.assertEqual({x['media']['id'] for x in resolve(self.app,self.chat['id'],job['id'])},{self.media['id'],'f'*32})
