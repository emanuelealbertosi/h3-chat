"""Real small CPU tensors and actual native-worker method; never load CUDA/models."""
import ast,contextlib,json,logging,math,os,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'runtime/vision/packages'),str(ROOT/'runtime/vision/core')]
if os.name=='nt':dll=os.add_dll_directory(str(ROOT/'runtime/vision/dlls'))
import torch
from comfy.nested_tensor import NestedTensor
from h3chat.video_longtake import context_guides,save_context,load_context,refine,signature
from h3chat.vendor_longtake.blend import blend_video


class RuntimeTests(unittest.TestCase):
    def test_worker_executes_refine_saves_delivered_tail_and_keeps_frame_count(self):
        tree=ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        events=[]
        def write(path,pixels,audio,frames):
            self.assertEqual(frames,24);self.assertEqual(len(pixels),39)
            Path(path).write_bytes(b'\0\0\0\x18ftypisomCPU')
        ns={'torch':torch,'math':math,'time':time,'json':json,'Path':Path,'logging':logging,
            'emit':lambda event,**value:events.append((event,value)),'write_video':write}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'video-worker.py','exec'),ns)
        worker=ns['Worker']();worker.torch=torch;worker.offload=False;worker.model=object()
        worker.images=lambda p:[];worker.memory_snapshot=lambda p:None
        worker.configure_attention=lambda *a:'pytorch';worker.attention_chunks=1
        worker.clip=SimpleNamespace(tokenize=lambda *a,**k:[],encode_from_tokens_scheduled=lambda x:[[torch.zeros(1,1,4),{}]])
        encoded=[]
        pixels=torch.arange(39).view(39,1,1,1).expand(39,32,32,3).float()/100
        def encode(frames):
            encoded.append(frames.clone());return torch.ones(1,24,7,2,2)
        worker.vae=SimpleNamespace(decode=lambda z:pixels.clone(),encode=encode)
        worker.audio_vae=object();worker.load_conditioners=Mock();worker.load_diffuser=Mock()
        base=NestedTensor((torch.zeros(1,24,12,2,2),torch.rand(1,32,2,65)))
        worker.h3=SimpleNamespace(_empty_av_latent=lambda *a:({'samples':base},39),
            MiniMaxH3SigmaShift=SimpleNamespace(execute=lambda m,*a:(m,)))
        calls=[]
        def sample(model,noise,steps,cfg,sampler,scheduler,positive,negative,latent,**kw):
            calls.append((steps,kw.get('denoise',1)))
            for n in range(steps):kw['callback'](n,None,None,steps)
            return NestedTensor((latent.unbind()[0]+1,latent.unbind()[1]))
        worker.comfy=SimpleNamespace(sample=SimpleNamespace(sample=sample,prepare_noise=lambda *a:base),nested_tensor=SimpleNamespace(NestedTensor=NestedTensor))
        helper=SimpleNamespace(conditioning_set_values=lambda p,v:p)
        decoder=SimpleNamespace(vae_decode_audio=lambda *a:{'sample_rate':24,'waveform':torch.ones(1,2,24)})
        with tempfile.TemporaryDirectory() as folder,patch.dict(sys.modules,{'node_helpers':helper,'comfy_extras.nodes_audio':decoder}):
            f=Path(folder);(f/'weights').write_bytes(b'fixture');worker.files={'diffusion':str(f/'weights'),'vae':str(f/'weights')}
            opts={'frames':24,'duration':1,'width':32,'height':32,'output_width':32,'output_height':32,'aspect':'1:1','aspect_source':'preset','format_image':None,'shift_video':12,'shift_audio':3,'seed':1,'cfg':1,'steps':2,'sampler':'euler','scheduler':'simple','longtake_enabled':True,'megapixels':.2}
            worker.generate({'options':opts,'plan':{'prompt':'Wave','images':[],'audios':[]},'images':[],'output':str(f/'video.mp4')})
            self.assertEqual(calls,[(2,1),(5,.55)])
            self.assertTrue(torch.equal(encoded[0],pixels[2:24]))
            self.assertTrue((f/'longtake-tail.safetensors').is_file())
            done=next(v['parameters'] for e,v in events if e=='done')
            self.assertEqual(done['output_frames'],24);self.assertTrue(done['longtake']['context_saved'])
            (f/'next').mkdir()
            worker.generate({'options':opts,'plan':{'prompt':'Continue','images':[],'audios':[]},'images':[],
                'output':str(f/'next/video.mp4'),'longtake_context':str(f/'longtake-tail.safetensors')})
            reports=[v['parameters'] for e,v in events if e=='done']
            self.assertEqual(reports[-1]['longtake']['context_frames'],22)
            self.assertEqual(reports[-1]['output_frames'],24)

    def test_refine_blends_video_preserves_audio_and_adds_five_actual_steps(self):
        base=NestedTensor((torch.zeros(1,24,72,2,2),torch.rand(1,32,2,400)))
        def sample(model,noise,steps,cfg,sampler,scheduler,pos,neg,latent,**kw):
            self.assertEqual((steps,kw['denoise']),(5,.55))
            self.assertTrue(torch.count_nonzero(kw['noise_mask'].unbind()[1])==0)
            return NestedTensor((torch.ones_like(base.unbind()[0]),torch.zeros_like(base.unbind()[1])))
        result=refine(sample,lambda *a:base,NestedTensor,torch,None,base,[],[],
            {'seed':1,'cfg':1,'sampler':'res_multistep','scheduler':'simple','frames':240},Mock())
        self.assertTrue(torch.equal(result.unbind()[1],base.unbind()[1]))
        self.assertTrue(torch.all(result.unbind()[0][:,:,:7]==0));self.assertTrue(torch.all(result.unbind()[0][:,:,14:]==1))

    def test_context_roundtrip_and_stale_or_different_canvas_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);media=p/'video.mp4';media.write_bytes(b'original')
            tail=torch.randn(1,24,7,4,4);save_context(p/'tail.safetensors',tail,'same',media)
            guides=load_context(p/'tail.safetensors','same',torch)
            self.assertEqual([g['resolved_frame_index'] for g in guides],[-22,-21,-17,-13,-9,-5,-4])
            self.assertTrue(torch.equal(torch.cat([g['latent'] for g in guides],dim=2),tail))
            with self.assertRaisesRegex(ValueError,'canvas'):load_context(p/'tail.safetensors','different',torch)
            media.write_bytes(b'changed original')
            with self.assertRaisesRegex(ValueError,'modificata'):load_context(p/'tail.safetensors','same',torch)

    def test_actual_packed_layout_keeps_video_and_audio_origins_with_negative_context(self):
        path=ROOT/'runtime/vision/core/comfy/ldm/minimax/model.py';tree=ast.parse(path.read_text())
        names={'_axis_from_sqrt_area','_frame_grid','_video_t_spans','_video_t_grid','_ref_t_span','_audio_grid','_video_grid','PackedLayout'}
        definitions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
        ns={'torch':torch,'math':math,'FRAME_RESCALE':5/3,'FRAME_PER_TOKEN':(1,4,4,4,4)}
        exec(compile(ast.Module(body=definitions,type_ignores=[]),str(path),'exec'),ns)
        layout=ns['PackedLayout'];empty=layout(10,72,4,4,400)
        guided=layout(10,72,4,4,400,keyframes=context_guides(torch.ones(1,24,7,4,4)))
        # Packed layouts expose stream spans and exact rotary coordinates.
        for key in ('audio','video'):
            a,b,_=next(s for s in empty.segments if s[2]==key)
            c,d,_=next(s for s in guided.segments if s[2]==key)
            self.assertTrue(torch.equal(empty.position_ids[a:b],guided.position_ids[c:d]))


if __name__=='__main__':unittest.main()
