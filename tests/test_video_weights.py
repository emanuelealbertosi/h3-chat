"""Safetensors bounds and buffer ownership, without a CUDA dependency."""
import ast
import gc
import json
import math
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]


class VideoWeightReaderTests(unittest.TestCase):
    def setUp(self):
        source=ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        definition=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='read_safetensors')
        namespace={'json':json,'math':math,'os':os}
        exec(compile(ast.Module(body=[definition],type_ignores=[]),'<video-weights>','exec'),namespace)
        self.load=namespace['read_safetensors']
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'model.safetensors'
        self.addCleanup(self.temp.cleanup)
        class Tensor:
            def __init__(self,buffer=b''):
                self.buffer=memoryview(buffer);self.storage=SimpleNamespace()
            def view(self,shape):self.shape=shape;return self
            def clone(self):return type(self)(memoryview(bytes(self.buffer)))
            def untyped_storage(self):return self.storage
        self.torch=SimpleNamespace(frombuffer=lambda buffer,**kw:Tensor(buffer),empty=lambda shape,**kw:Tensor().view(shape))
        self.types={'U8':SimpleNamespace(itemsize=1)}

    def write(self,header,data=b'\x03\x07'):
        payload=json.dumps(header).encode()
        self.path.write_bytes(struct.pack('<Q',len(payload))+payload+data)

    def test_writable_buffer_survives_file_close_with_metadata_and_empty_tensors(self):
        self.write({'weights':{'dtype':'U8','shape':[2],'data_offsets':[0,2]},
            'empty':{'dtype':'U8','shape':[0],'data_offsets':[2,2]},'__metadata__':{'quantization':'int8'}})
        tensors,meta=self.load(self.path,self.torch,self.types)
        gc.collect()
        self.assertEqual(tensors['weights'].buffer.tobytes(),b'\x03\x07')
        self.assertEqual(meta,{'quantization':'int8'})
        self.assertFalse(tensors['weights'].buffer.readonly)
        tensors['weights'].buffer[0]=9
        self.assertEqual(tensors['weights'].buffer.tobytes(),b'\x09\x07')
        self.assertEqual(tensors['empty'].shape,[0])
        # The model file is closed and untouched, independent of tensor writes.
        self.assertEqual(self.path.read_bytes()[-2:],b'\x03\x07')

    def test_rejects_out_of_bounds_shapes_types_and_offsets(self):
        for changes in ({'data_offsets':[0,3]},{'data_offsets':[-1,1]}, {'shape':[3]},
                {'shape':[-1]}, {'dtype':'UNKNOWN'}, {'data_offsets':[False,2]}):
            with self.subTest(changes=changes):
                self.write({'weights':{'dtype':'U8','shape':[2],'data_offsets':[0,2]}|changes})
                with self.assertRaises(ValueError):self.load(self.path,self.torch,self.types)

    def test_rejects_incomplete_and_oversized_headers(self):
        for raw in (b'',struct.pack('<Q',50)+b'{}',struct.pack('<Q',100_000_001)):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):self.load(self.path,self.torch,self.types)


if __name__=='__main__':unittest.main()
