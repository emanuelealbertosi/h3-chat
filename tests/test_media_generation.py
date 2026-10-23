import base64,json,struct,threading,unittest
from pathlib import Path
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.media_generation import get,embed_png,png_recipe,record_image


class RecipeTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def image(self,seed=42,prompt='Una pera',parameters=None,refs=None):
        from PIL import Image
        chat=self.app.store.create_chat()['id']
        ident=self.app.send(chat,{'prompt':prompt,'image_model':self.qwen['id'],'assistant':False})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True)
        Image.new('RGB',(512,512),'#247').save(folder/'image.png')
        p={'width':512,'height':512,'steps':25,'cfg':1,'seed':seed,'sampler':'euler','scheduler':'simple','negative_prompt':'','strength':1}|(parameters or {})
        media={'id':ident,'name':'image.png','mime':'image/png','path':f'outputs/{ident}/image.png'}
        meta={'model':self.qwen['name'],'image_model_id':self.qwen['id'],'image_prompt':prompt,'image_parameters':p,'references':refs or [],'loras':[]}
        self.app.store.update_answer(job,'Immagine','done',[media],meta)
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        return media,p

    def test_specific_old_image_gets_its_seed_prompt_and_settings_not_latest_seed(self):
        older,p=self.image(0,'Prompt originale <script>come testo</script>')
        self.image(999,'Un’altra immagine')
        recipe=get(self.app,older['id'])
        self.assertEqual(recipe['parameters']['seed'],0)
        self.assertEqual(recipe['prompt'],'Prompt originale <script>come testo</script>')
        self.assertEqual(recipe['model']['id'],self.qwen['id']);self.assertTrue(recipe['reusable'],recipe['warnings'])
        self.assertEqual(recipe['source'],'history')

    def test_missing_reference_and_missing_model_block_silent_substitution(self):
        missing={'id':'f'*32,'name':'Originale assente','mime':'image/png'}
        media,p=self.image(refs=[missing])
        recipe=get(self.app,media['id']);self.assertFalse(recipe['reusable']);self.assertIn('Originale assente',' '.join(recipe['warnings']))
        self.app.catalog.pop(self.qwen['id']);self.assertFalse(get(self.app,media['id'])['reusable'])

    def test_recipe_dimensions_use_the_original_model_grid(self):
        media,p=self.image(parameters={'width':774,'height':1376,'aspect':'9:16','megapixels':1.05})
        model=self.app.catalog[self.qwen['id']]
        with patch.object(self.app.engine,'require_model'):
            for architecture,dimensions,expected in [('moss',(774,1376),True),('qwen-edit',(774,1376),False)]:
                with self.subTest(architecture=architecture):
                    model['architecture']=architecture
                    record_image(self.app,media,model,p|{'width':dimensions[0],'height':dimensions[1]},'Originale',[],[])
                    recipe=get(self.app,media['id'])
                    self.assertEqual(recipe['reusable'],expected,recipe['warnings'])

    def test_png_recipe_roundtrip_preserves_compressed_pixels_and_recovers_on_upload(self):
        media,p=self.image(seed=17);file=self.app.data/media['path']
        def image_data(raw):
            chunks=[];offset=8
            while offset+12<=len(raw):
                size,kind=struct.unpack('>I4s',raw[offset:offset+8]);end=offset+12+size
                if kind==b'IDAT':chunks.append(raw[offset:end])
                offset=end
            return chunks
        before=image_data(file.read_bytes())
        record_image(self.app,media,self.qwen,p,'Prompt effettivo',[],[])
        self.assertEqual(image_data(file.read_bytes()),before)
        self.assertEqual(png_recipe(file)['parameters']['seed'],17)
        from PIL import Image
        with Image.open(file) as decoded:self.assertIn('h3_creation',decoded.info)
        self.assertTrue(media['generation']['metadata_embedded'])
        uploaded=self.app.upload({'name':'Scaricata.png','data':base64.b64encode(file.read_bytes()).decode()})
        recipe=get(self.app,uploaded['id'])
        self.assertEqual(recipe['source'],'png');self.assertEqual(recipe['prompt'],'Prompt effettivo');self.assertTrue(recipe['reusable'])
        self.assertTrue(file.with_name('image.png.h3.json').exists())

    def test_exact_batch_member_and_completed_image_survive_other_seed_and_failed_batch(self):
        media,p=self.image(11);other,q=self.image(22)
        with self.app.store.connect() as db:
            row=db.execute('SELECT message_id FROM jobs WHERE id=?',(media['id'],)).fetchone()
            first=media|{'generation':p|{'prompt':'Primo','image_model_id':self.qwen['id'],'model':self.qwen['name'],'loras':[]}}
            second=other|{'generation':q|{'prompt':'Secondo','image_model_id':self.qwen['id'],'model':self.qwen['name'],'loras':[]}}
            db.execute("UPDATE messages SET media=?,meta=?,status='failed' WHERE id=?",(json.dumps([first,second]),json.dumps({'image_batch':True}),row['message_id']))
        recipe=get(self.app,media['id']);self.assertEqual(recipe['parameters']['seed'],11);self.assertEqual(recipe['prompt'],'Primo')

    def test_private_paths_and_credentials_are_not_exported_and_foreign_id_is_rejected(self):
        media,p=self.image(parameters={'api_key':'PRIVATE','model_file':'C:/private/weights.safetensors'})
        recipe=get(self.app,media['id']);text=json.dumps(recipe)
        self.assertNotIn('PRIVATE',text);self.assertNotIn('C:/private',text);self.assertEqual(recipe['parameters']['model_file'],'weights.safetensors')
        with self.assertRaises(ValueError):get(self.app,'a'*32)

    def test_forged_embedded_recipe_is_validated_before_reuse(self):
        media,p=self.image();file=self.app.data/media['path']
        embed_png(file,{'version':1,'kind':'image','model':{'id':[]},'parameters':{},'references':[],'loras':[]})
        with self.assertRaisesRegex(ValueError,'non validi'):get(self.app,media['id'])

    def test_video_recipe_is_recoverable_without_modifying_mp4(self):
        media,p=self.image();path=self.app.data/media['path'];mp4=path.with_suffix('.mp4');mp4.write_bytes(b'video unchanged')
        video=media|{'id':'b'*32,'path':str(mp4.relative_to(self.app.data)).replace('\\','/'),'mime':'video/mp4','name':'video.mp4','generation':{'seed':444,'duration':10,'scene_parameters':[{'seed':3},{'seed':4}]}}
        row=self.app.store.one('SELECT * FROM jobs WHERE id=?',(media['id'],))
        self.app.store.update_answer(row,'Video','done',[video],{})
        result=get(self.app,video['id']);self.assertEqual(result['kind'],'video');self.assertEqual(result['parameters']['seed'],444);self.assertFalse(result['reusable'])
        self.assertEqual(result['parameters']['scene_parameters'][1]['seed'],4);self.assertEqual(mp4.read_bytes(),b'video unchanged')


if __name__=='__main__':unittest.main()
