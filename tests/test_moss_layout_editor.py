import copy,json,unittest
from h3chat.moss_layout import editor_draft,explicit
from h3chat.image_options import options
from h3chat.external_models import PROFILES
from h3chat.store import DEFAULTS
from h3chat.poster_reference_check import diagnose

DRAFT={'width':1536,'height':1024,'bbox_coord_space':'abs','bbox_format':'xyxy',
 'summary':{'caption':'A ceramic cup and a title.','canvas':'single'},'items':[
 {'label':'object','caption':'A ceramic cup','bbox':[176,224,800,864]},
 {'label':'text','caption':'Green text','text':'Ciao!\nSeed 123, 512x768, CFG 20, 9:16','bbox':[928,272,1408,448]}]}

class EditorDraftTests(unittest.TestCase):
 def test_official_example_compiles_exactly_and_preserves_text(self):
  before=copy.deepcopy(DRAFT);out=editor_draft(json.dumps(DRAFT));compiled=json.loads(out['prompt'])
  self.assertEqual(compiled['items'][0]['bbox'],[-288,-592,352,32]);self.assertEqual(compiled['items'][1]['text'],DRAFT['items'][1]['text']);self.assertEqual(DRAFT,before)
  self.assertEqual(explicit(json.dumps(DRAFT)),out['prompt'])
 def test_canvas_overrides_settings_but_words_in_caption_are_not_parameters(self):
  model={'id':'moss',**PROFILES['moss']};settings=DEFAULTS|{'seed':42,'width':512,'height':512}
  result=options(model,settings,json.dumps(DRAFT))
  self.assertEqual((result['width'],result['height'],result['seed'],result['cfg']),(1536,1024,42,3))
  self.assertFalse(result['preserve_reference_aspect'])
 def test_rejects_invalid_geometry_without_clipping(self):
  for changes in ({'width':1500},{'width':True},{'height':8192},{'bbox_coord_space':'abs','bbox_format':'xyxy','items':[]}):
   with self.subTest(changes=changes),self.assertRaises(ValueError):editor_draft(json.dumps(DRAFT|changes))
  for bbox in ([0,0,1600,100],[50,0,20,100],[False,0,100,100],[0,0,float('nan'),100]):
   value=copy.deepcopy(DRAFT);value['items'][0]['bbox']=bbox
   with self.assertRaises(ValueError):editor_draft(json.dumps(value))
 def test_unrelated_prompts_are_unchanged(self):
  self.assertIsNone(editor_draft('A landscape.'));self.assertIsNone(editor_draft('{not json'))

class PosterEvidenceTests(unittest.TestCase):
 def test_verified_logo_contacts_are_evidence_but_unverified_captions_are_not(self):
  report={'width':1000,'height':1400,'images':[],'visible_text':'info@example.org · 0585 12345'}
  region={'kind':'image','role':'logo','text':'info@example.org · 0585 12345','legibility':'clear'}
  self.assertEqual(diagnose(report,{'plan':{'regions':[region]}},[]),[])
  self.assertIn('unverified_contacts',str(diagnose(report,{'plan':{'regions':[region|{'legibility':'uncertain'}]}},[])))
 def test_decorative_figure_has_its_own_area_budget_but_must_be_visible(self):
  asset={'id':'art','role':'decoration','source_box':[.05,.3,.9,.4]};report={'width':1000,'height':1000,'images':[{'id':'art','visible':True,'width':200,'height':300}],'visible_text':''}
  info={'plan':{'regions':[]}};self.assertEqual(diagnose(report,info,[asset]),[])
  report['images'][0]['width']=20;self.assertIn('hero_too_small',str(diagnose(report,info,[asset])))
  report['images']=[];self.assertIn('missing_visible_image',str(diagnose(report,info,[asset])))
 def test_academic_year_is_not_an_unverified_phone_number(self):
  report={'width':1000,'height':1400,'images':[],'visible_text':'Anno scolastico 2026-2027'}
  self.assertEqual(diagnose(report,{'plan':{'regions':[]}},[]),[])
