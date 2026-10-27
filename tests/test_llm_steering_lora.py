"""Rank-one adapter format, fixed scale, true layer subsetting and CLI staging."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from h3chat import llm_steering as steering
from h3chat.llm_steering_lora import inspect,subset


def fixture(layers=(1,2,3),alpha=1.,bad_shape=False):
    def text(s):
        raw=s.encode();return struct.pack('<Q',len(raw))+raw
    metas={'general.architecture':'qwen35','general.type':'adapter','adapter.type':'lora'}
    data=bytearray();tensors=[]
    for layer in layers:
        for module in ('ffn_down','attn_output' if layer%4==3 else 'ssm_out'):
            for side in ('a','b'):
                shape=(17408 if module=='ffn_down' else 6144,1) if side=='a' else (1,5120)
                if bad_shape and not tensors:shape=(99,1)
                data.extend(b'\0'*((-len(data))%32));offset=len(data)
                data.extend(struct.pack('<f',layer/100)*(shape[0]*shape[1]))
                tensors.append((f'blk.{layer}.{module}.weight.lora_{side}',shape,offset))
    raw=b'GGUF'+struct.pack('<IQQ',3,len(tensors),4)
    for key,value in metas.items():raw+=text(key)+struct.pack('<I',8)+text(value)
    raw+=text('adapter.lora.alpha')+struct.pack('<If',6,alpha)
    for name,shape,offset in tensors:raw+=text(name)+struct.pack('<IQQIQ',2,*shape,0,offset)
    return raw+b'\0'*((-len(raw))%32)+data


class SteeringLora(unittest.TestCase):
    def test_lossless_subset_keeps_real_layer_numbers(self):
        raw=fixture();info=inspect(raw);self.assertEqual(info['layers'],{1,2,3})
        selected=subset(raw,info,2,3);reduced=inspect(selected)
        self.assertEqual(reduced['layers'],{2,3});self.assertEqual(len(reduced['tensors']),8)
        original={t['name']:raw[info['payload_start']+t['offset']:info['payload_start']+t['offset']+t['bytes']] for t in info['tensors']}
        for t in reduced['tensors']:
            self.assertEqual(selected[reduced['payload_start']+t['offset']:reduced['payload_start']+t['offset']+t['bytes']],original[t['name']])

    def test_invalid_alpha_shapes_zero_mtp_and_nonfinite_rejected(self):
        for raw in (fixture(alpha=2),fixture(bad_shape=True),fixture(layers=(0,)),fixture(layers=(64,)),fixture()[:-5]):
            with self.assertRaises(ValueError):inspect(raw)
        raw=bytearray(fixture());i=inspect(raw);struct.pack_into('<f',raw,i['payload_start'],float('nan'))
        with self.assertRaisesRegex(ValueError,'NaN'):inspect(raw)

    def test_scale_and_mode_guard_before_launch(self):
        settings=steering.DEFAULTS|{'llm_steering_enabled':True,'llm_steering_mode':'glp_lora','llm_steering_file':'F:/adapter.gguf','llm_steering_strength':2}
        with self.assertRaisesRegex(ValueError,'scala|scala|Scala'):steering.validate(settings)
        with self.assertRaises(ValueError):steering.validate(settings|{'llm_steering_mode':'project'})

    def test_staging_uses_lora_not_additive_and_changes_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);file=root/'adapter.gguf';file.write_bytes(fixture())
            settings=steering.DEFAULTS|{'llm_steering_enabled':True,'llm_steering_mode':'glp_lora','llm_steering_file':str(file),'llm_steering_strength':1,'llm_steering_layer_start':2,'llm_steering_layer_end':3}
            meta={'general.architecture':'qwen35','qwen35.embedding_length':5120,'qwen35.block_count':65}
            with patch('h3chat.models.metadata',return_value=meta):result=steering.prepare(root,{},settings,{'model':root/'base.gguf'})
            self.assertEqual(result['args'][0],'--lora');self.assertNotIn('--control-vector-scaled',result['args'])
            self.assertEqual(inspect((result['cwd']/result['args'][1]).read_bytes())['layers'],{2,3})
            before=steering.fingerprint(settings);self.assertNotEqual(before,steering.fingerprint(settings|{'llm_steering_layer_start':1}))
            self.assertIsNone(steering.prepare(root,{},settings|{'llm_steering_enabled':False},{}))
