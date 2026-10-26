"""Structural control-vector and managed-launch tests; no trained weights/GPU."""
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from h3chat import llm_steering as steering
from h3chat.llm_options import BASE,merge,validate
from h3chat.store import DEFAULTS
from test_mtp import mtp_gguf
import test_llm_acceleration as acceleration_fixture


def vector(path,width=5120,layers=(1,2),hint='qwen35',extra=None,item=.125):
    def string(value):
        raw=value.encode();return struct.pack('<Q',len(raw))+raw
    meta={'general.architecture':'controlvector','controlvector.model_hint':hint}|(extra or {})
    raw=b'GGUF'+struct.pack('<IQQ',3,len(layers),len(meta))
    for key,value in meta.items():raw+=string(key)+struct.pack('<I',8)+string(value)
    stride=(width*4+31)//32*32
    for i,layer in enumerate(layers):raw+=string('direction.'+str(layer))+struct.pack('<IQIQ',1,width,0,i*stride)
    raw+=b'\0'*((-len(raw))%32)
    for _ in layers:raw+=struct.pack('<f',item)*width+b'\0'*(stride-width*4)
    path=Path(path);path.write_bytes(raw);return path


class SteeringTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.file=vector(self.root/'vector.gguf')
        model_file=mtp_gguf(self.root/'model.gguf',blocks=65,extra={'qwen35.embedding_length':5120})
        self.files={'model':model_file};self.settings=DEFAULTS|{'llm_steering_enabled':True,'llm_steering_file':str(self.file),'llm_steering_layer_end':2,'llm_steering_strength':.03}

    def test_disabled_is_identical_and_does_not_read_files(self):
        settings=self.settings|{'llm_steering_enabled':False,'llm_steering_file':'missing'}
        self.assertIsNone(steering.prepare(self.root,{},settings,{}))
        self.assertIsNone(steering.fingerprint(settings))

    def test_stages_original_bytes_and_uses_relative_name_not_windows_drive(self):
        result=steering.prepare(self.root,{},self.settings,self.files)
        arg=result['args'][1];name,strength=arg.split(':')
        self.assertEqual(float(strength),.03);self.assertNotIn('\\',name);self.assertEqual(len(name),69)
        self.assertEqual((result['cwd']/name).read_bytes(),self.file.read_bytes())
        self.assertEqual(result['args'][-2:],[1,2])

    def test_qwen_name_alone_dimension_hint_and_projection_are_rejected(self):
        for options in ({'width':2560},{'hint':'qwen3next'},{'extra':{'glp.mode':'project'}}):
            vector(self.file,**options)
            with self.assertRaises(ValueError):steering.prepare(self.root,{},self.settings,self.files)
        vector(self.file)
        with self.assertRaisesRegex(ValueError,'API'):steering.prepare(self.root,{'api':True},self.settings,self.files)

    def test_complete_selected_layers_required_and_mtp_head_excluded(self):
        for layers in ((1,3),(1,2,64)):
            vector(self.file,layers=layers)
            with self.assertRaises(ValueError):steering.prepare(self.root,{},self.settings,self.files)
        vector(self.file)
        with self.assertRaises(ValueError):steering.prepare(self.root,{},self.settings|{'llm_steering_layer_end':64},self.files)

    def test_malformed_nonfinite_empty_and_duplicate_vectors_rejected(self):
        for options in ({'item':float('nan')},{'item':float('inf')},{'item':0},{'layers':(1,1)}):
            vector(self.file,**options)
            with self.assertRaises(ValueError):steering.read_vector(self.file)
        vector(self.file);self.file.write_bytes(self.file.read_bytes()[:-5])
        with self.assertRaises(ValueError):steering.read_vector(self.file)
        with self.assertRaises(ValueError):steering.inspect_bytes(b'GGUF'+b'\0'*steering.MAX_BYTES)

    def test_strength_content_and_range_change_the_session_identity(self):
        first=steering.fingerprint(self.settings)
        self.assertNotEqual(first,steering.fingerprint(self.settings|{'llm_steering_strength':.02}))
        vector(self.file,item=.25)
        self.assertNotEqual(first,steering.fingerprint(self.settings))

    def test_settings_are_per_model_and_off_by_default(self):
        current=DEFAULTS|{'chat_model':'a'}
        self.assertFalse(BASE['llm_steering_enabled'])
        saved=merge(current,{k:self.settings[k] for k in steering.DEFAULTS})
        switched=merge(saved,{'chat_model':'b'})
        self.assertFalse(switched['llm_steering_enabled'])
        restored=merge(switched,{'chat_model':'a'})
        self.assertTrue(restored['llm_steering_enabled']);self.assertEqual(restored['llm_steering_strength'],.03)
        for patch_value in ({'llm_steering_enabled':'yes'},{'llm_steering_strength':math.nan},{'llm_steering_layer_start':0},{'llm_steering_layer_end':True},{'llm_steering_file':'a\0b'}):
            with self.assertRaises(ValueError):validate(patch_value)

    def test_invalid_selection_is_rejected_before_preferences_are_saved(self):
        from h3chat.service import Service
        app=Service(Path(__file__).resolve().parents[1],self.root/'app-data',start_worker=False)
        self.addCleanup(app.close)
        model=app.external_model({'profile':'chat','name':'Structural Qwen','files':{'model':str(self.files['model'])},'projector_mode':'off'})
        patch={k:self.settings[k] for k in steering.DEFAULTS}|{'chat_model':model['id']}
        app.save_settings(patch)
        self.file.write_bytes(b'broken')
        with self.assertRaises(ValueError):app.save_settings({'llm_steering_strength':.04})
        self.assertEqual(app.store.settings()['llm_steering_strength'],.03)


class SteeringLaunchTests(unittest.TestCase):
    def setUp(self):
        self.base=acceleration_fixture.AccelerationTests();self.base.setUp()
        self.addCleanup(self.base.doCleanups);self.addCleanup(self.base.tearDown)
        self.file=vector(self.base.root/'steering.gguf',layers=tuple(range(1,64)))
        self.settings=self.base.settings|{'llm_steering_enabled':True,'llm_steering_file':str(self.file),'llm_steering_strength':.03}
        self.launches=[]
        def start(session,args,**kwargs):
            self.launches.append((session,list(args),kwargs));session.process=acceleration_fixture.Process()
        self.mock=patch('h3chat.residency.Session.start',start);self.mock.start();self.addCleanup(self.mock.stop)

    def test_optimized_mtp_managed_reuse_change_and_disable(self):
        first=self.base.load(self.settings);args=self.launches[-1][1]
        self.assertIn('--control-vector-scaled',args);self.assertIn('--spec-draft-n-max',args)
        self.assertEqual(args[args.index('--control-vector-layer-range')+1:][:2],[1,63])
        self.assertEqual(first.snapshot()['steering']['strength'],.03)
        self.assertIs(first,self.base.load(self.settings));self.assertEqual(len(self.launches),1)
        second=self.base.load(self.settings|{'llm_steering_strength':.04})
        self.assertFalse(first.alive());self.assertIsNot(first,second)
        plain=self.base.load(self.settings|{'llm_steering_enabled':False})
        self.assertFalse(second.alive());self.assertNotIn('--control-vector-scaled',self.launches[-1][1])
        self.assertNotIn('cwd',self.launches[-1][2]);self.assertIsNone(plain.snapshot()['steering'])

    def test_bad_vector_does_not_interrupt_an_existing_session(self):
        first=self.base.load();self.file.write_bytes(b'broken')
        with self.assertRaises(ValueError):self.base.load(self.settings)
        self.assertTrue(first.alive());self.assertEqual(len(self.launches),1)
