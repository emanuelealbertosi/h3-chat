import base64,copy,json,unittest
from test_visual_models import VisualModelsTests as _Fixture
from test_image_batch import PNG
from test_poster_visual import layout
from h3chat import poster_visual as visual
from h3chat.poster_typography import revise
from h3chat.posters import options
from h3chat.slides import FORMATS,encode

class PosterTypographyTests(unittest.TestCase):
    setUp=_Fixture.setUp
    tearDown=_Fixture.tearDown
    def artifact(self):
        item=self.app.upload({'name':'poster.png','data':base64.b64encode(PNG).decode()});opts=options(value={'composition':'moss_layout'});w,h=FORMATS['A3'];v=layout();v['zones'][1].update(role='body',text='INCONTRO 1 — IDEE\nUna descrizione da conservare.',bbox=[60,700,940,950]);v=visual.validate(v,w,h,5,self.app.root,opts)
        page={'title':'Prova','status':'ready','html':visual.compose(v,item['id'],w,h),'nodes':[],'notes':'','sources':[],'poster_layout':v,'poster_background':item['id']}
        deck={'version':1,'engine':'llm','document_kind':'poster','poster':opts,'format':'A3','title':'Prova','theme':'lagoon','typography':'modern','design':'professional','detail':'concise','motion':'static','references':[],'active':0,'pages':[page]}
        chat=self.app.store.create_chat()['id'];return chat,self.app.store.canvas_history.save(chat,{'title':'Prova','content':encode(deck),'media':[item]},editable=True)
    def test_restylings_are_revisions_keep_exact_image_and_global_preferences(self):
        chat,value=self.artifact();before=self.app.store.settings();new=revise(self.app,chat,{'artifact_id':value['id'],'page':1,'typography':{'lettering':'comic','text_effect':'outline'}})
        self.assertEqual(new['media'],value['media']);self.assertEqual(self.app.store.settings(),before);self.assertNotEqual(new['id'],value['id']);self.assertIn('font-family:Bangers',new['content']);self.assertEqual(self.app.store.canvas_history.get(chat,value['id'])['content'],value['content'])
    def test_manual_text_changes_are_not_discarded(self):
        chat,value=self.artifact();value['content']=value['content'].replace('Una descrizione da conservare.</span>','Testo cambiato manualmente.</span>');changed=self.app.store.canvas_history.save(chat,value,edit_id=value['id'],editable=True)
        with self.assertRaisesRegex(ValueError,'modificato manualmente'):revise(self.app,chat,{'artifact_id':changed['id'],'page':1,'typography':{'lettering':'neon'}})

if __name__=='__main__':unittest.main()
