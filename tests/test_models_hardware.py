import io
import json
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from h3chat.models import metadata, discover_local, inspect_model, thinking_parameters, THINK_LEVELS
from h3chat.hardware import assess_model
from h3chat.engine import Engine
from h3chat.store import DEFAULTS


def gguf(path, **values):
    def string(s):
        raw=s.encode();return struct.pack('<Q',len(raw))+raw
    data=b'GGUF'+struct.pack('<IQQ',3,0,len(values))
    for key,value in values.items():
        data+=string(key)+struct.pack('<I',8 if isinstance(value,str) else 4)
        data+=string(value) if isinstance(value,str) else struct.pack('<I',value)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return path


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.base=gguf(self.root/'models/local/Test/model.gguf',**{'general.architecture':'qwen3','general.name':'Test',
            'qwen3.block_count':28,'tokenizer.chat_template':'{% if enable_thinking %}<think>{% endif %}'})
    def tearDown(self): self.tmp.cleanup()

    def test_projector_auto_detection_is_folder_scoped_and_rechecked(self):
        model=discover_local(self.root)[0]
        self.assertTrue(inspect_model(self.root,model)['ready'])
        self.assertFalse(inspect_model(self.root,model)['vision']['enabled'])
        gguf(self.root/'models/local/Other/mmproj.gguf',**{'general.architecture':'clip'})
        self.assertFalse(inspect_model(self.root,model)['vision']['enabled'])
        projector=gguf(self.base.parent/'mmproj.gguf',**{'general.architecture':'clip'})
        traits=inspect_model(self.root,model)
        self.assertTrue(traits['vision']['enabled'])
        engine=Engine(self.root,self.root/'data',{model['id']:model})
        self.assertEqual(Path(engine.model_files(model)['mmproj']),projector)
        second=gguf(self.base.parent/'mmproj-other.gguf',**{'general.architecture':'clip'})
        self.assertFalse(inspect_model(self.root,model)['vision']['enabled'])
        self.assertIn('Più mmproj',inspect_model(self.root,model)['vision']['warning'])
        self.assertNotIn('mmproj',engine.model_files(model))
        second.unlink();projector.unlink()
        self.assertNotIn('mmproj',engine.model_files(model))

    def test_missing_catalog_projector_preserves_verified_text_mode(self):
        projector=gguf(self.base.parent/'mmproj.gguf',**{'general.architecture':'clip'})
        files=[{'role':role,'path':p.relative_to(self.root).as_posix(),'size':p.stat().st_size,'sha256':'a'*64}
            for role,p in [('model',self.base),('mmproj',projector)]]
        model={'id':'catalog-test','name':'Test','capabilities':['chat','vision'],'files':files,'max_refs':4}
        (self.root/'models/catalog-test.ready.json').write_text(json.dumps({'files':[{k:f[k] for k in ('path','size','sha256')} for f in files]}))
        self.assertTrue(inspect_model(self.root,model)['vision']['enabled'])
        projector.unlink()
        traits=inspect_model(self.root,model)
        self.assertTrue(traits['ready']);self.assertFalse(traits['vision']['enabled']);self.assertFalse(traits['complete'])
        self.assertIn('mmproj',traits['vision']['warning'])

    def test_invalid_metadata_and_template_capability(self):
        self.assertEqual(metadata(self.base)['qwen3.block_count'],28)
        model=discover_local(self.root)[0]
        self.assertTrue(inspect_model(self.root,model)['thinking']['supported'])
        self.base.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,10000000))
        self.assertEqual(metadata(self.base),{})
        self.assertEqual(discover_local(self.root),[])

    def test_thinking_budgets_reserve_answer_and_router_is_always_off(self):
        model={'thinking':{'supported':True,'mode':'budget'}}
        budgets=[]
        for level in THINK_LEVELS:
            body=thinking_parameters(model,DEFAULTS|{'think_level':level})
            budgets.append(body['reasoning_budget_tokens'])
            self.assertEqual(body['chat_template_kwargs']['enable_thinking'],level!='off')
            self.assertLessEqual(body['reasoning_budget_tokens'],DEFAULTS['max_tokens']-256)
        self.assertEqual(len(set(budgets)),5);self.assertEqual(budgets,sorted(budgets))
        for override in ({'thinking':{'supported':False}},{}):
            self.assertEqual(thinking_parameters(override,DEFAULTS|{'think_level':'high'})['reasoning_budget_tokens'],0)
        self.assertEqual(thinking_parameters(model,DEFAULTS|{'think_level':'xhigh'},router=True)['reasoning_effort'],'none')
        native={'thinking':{'supported':True,'mode':'native','native_xhigh':False}}
        self.assertEqual(thinking_parameters(native,DEFAULTS|{'think_level':'med'})['reasoning_effort'],'medium')
        self.assertEqual(thinking_parameters(native,DEFAULTS|{'think_level':'xhigh'})['reasoning_effort'],'high')

    def test_streaming_reasoning_never_leaks_into_answer_or_canvas_json(self):
        model={'thinking':{'supported':True,'mode':'budget'}}
        engine=Engine(self.root,self.root,{})
        engine.active_model=model;engine.port=1000;engine.key='test'
        output=[];thinking=[];requests=[]
        def response(req,**kwargs):
            requests.append(json.loads(req.data))
            return io.BytesIO(b'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"42"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
        with patch('h3chat.engine.urllib.request.urlopen',side_effect=response):
            content,finish=engine.completion([],DEFAULTS|{'think_level':'high'},threading.Event(),on_text=output.append,on_reasoning=lambda:thinking.append(True))
        self.assertEqual((content,finish),('42','stop'));self.assertTrue(thinking)
        self.assertNotIn('private',''.join(output));self.assertEqual(requests[0]['reasoning_budget_tokens'],512)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.model={'id':'test','name':'Test','capabilities':['chat'],'files':[{'role':'model','size':4*1024**3}],
            'parameters':{'layers':32,'embedding':4096,'heads':32,'kv_heads':8}}
        self.hardware={'ram':{'total_mb':32768,'free_mb':24576},'gpu':[{'name':'GPU','vendor':'NVIDIA','total_mb':16384,'free_mb':14000}]}
        self.settings=DEFAULTS|{'profile':'balanced','gpu_layers':99}

    def test_ok_offload_oom_and_unknown_are_distinct(self):
        self.assertEqual(assess_model(self.model,self.settings,self.hardware)['status'],'ok')
        self.assertEqual(assess_model(self.model,self.settings|{'gpu_layers':10},self.hardware)['status'],'offload')
        busy=self.hardware|{'gpu':[self.hardware['gpu'][0]|{'free_mb':700}]}
        result=assess_model(self.model,self.settings,busy)
        self.assertEqual(result['status'],'offload');self.assertTrue(result['oom_risk'])
        self.assertEqual(result['recommended_patch']['gpu_layers'],0)
        low=busy|{'ram':{'total_mb':8192,'free_mb':256}}
        self.assertEqual(assess_model(self.model,self.settings,low)['status'],'oom')
        unknown=self.hardware|{'gpu':[self.hardware['gpu'][0]|{'free_mb':None}]}
        self.assertEqual(assess_model(self.model,self.settings,unknown)['status'],'unknown')

    def test_context_and_reference_growth_increase_memory(self):
        model=self.model|{'vision':{'expected':True,'projector_size':1024**3}}
        one=assess_model(model,self.settings,self.hardware,1)
        four=assess_model(model,self.settings|{'context':16384},self.hardware,4)
        self.assertGreater(four['ram_gb'],one['ram_gb']);self.assertGreater(four['vram_gb'],one['vram_gb'])
        # CUDA cannot use a non-NVIDIA GPU; multiple GPUs are never summed.
        amd=self.hardware|{'gpu':[self.hardware['gpu'][0]|{'vendor':'AMD'}]}
        self.assertEqual(assess_model(model,self.settings|{'backend':'cuda'},amd)['status'],'unknown')
        multiple=self.hardware|{'gpu':self.hardware['gpu']*2}
        self.assertEqual(assess_model(model,self.settings,multiple)['status'],'unknown')

    def test_diffusion_resolution_and_cpu_ram_shortage(self):
        model={'id':'image','name':'Image','architecture':'flux2','capabilities':['create','edit'],
            'files':[{'role':'diffusion','size':3*1024**3},{'role':'llm','size':2*1024**3}]}
        small=assess_model(model,self.settings,self.hardware,1)
        large=assess_model(model,self.settings|{'width':1536,'height':1536},self.hardware,4)
        self.assertGreater(large['vram_gb'],small['vram_gb'])
        low=self.hardware|{'ram':{'free_mb':1024}}
        self.assertEqual(assess_model(model,self.settings|{'profile':'cpu'},low)['status'],'oom')


if __name__=='__main__': unittest.main()
