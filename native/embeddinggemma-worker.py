"""Isolated EmbeddingGemma 2 text/image inference with native HF classes."""
import json,logging,os,sys,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];VISION=ROOT/'runtime/vision';RUNTIME=ROOT/'runtime/embeddinggemma2'
dll=os.add_dll_directory(str(VISION/'dlls')) if os.name=='nt' and (VISION/'dlls').is_dir() else None
sys.path[:0]=[str(ROOT),str(RUNTIME/'packages'),str(VISION/'packages')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_XET='1',HF_HOME=str(RUNTIME/'cache'))
wire=sys.stdout;sys.stdout=sys.stderr
logging.basicConfig(level=logging.WARNING,stream=sys.stderr)
def emit(event,**values):wire.write(json.dumps({'event':event,**values},ensure_ascii=False)+'\n');wire.flush()

class Worker:
    def load(self,request):
        import torch
        from transformers import AutoConfig,AutoModel,AutoTokenizer,AutoProcessor
        from h3chat.embeddinggemma2 import checkpoint,DIMENSIONS
        folder,_=checkpoint(request['path']);device=request['device']
        if device not in ('cpu','cuda'):raise ValueError('Dispositivo embedding non valido.')
        if device=='cuda' and not torch.cuda.is_available():raise ValueError('EmbeddingGemma 2 GPU richiede NVIDIA CUDA. Seleziona CPU nelle Preferenze.')
        torch.set_num_threads(max(1,min(int(request.get('threads',4)),16)))
        self.visual=bool(request.get('visual'));self.device=device;self.torch=torch
        self.dtype=torch.bfloat16 if device=='cuda' and torch.cuda.is_bf16_supported() else torch.float32
        config=AutoConfig.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
        config.audio_config=None
        if not self.visual:config.vision_config=None
        emit('stage',message='RAG · caricamento EmbeddingGemma 2 · '+('GPU' if device=='cuda' else 'CPU'))
        self.model,info=AutoModel.from_pretrained(str(folder),config=config,dtype=self.dtype,
            local_files_only=True,trust_remote_code=False,use_safetensors=True,attn_implementation='sdpa',output_loading_info=True)
        if info.get('missing_keys') or info.get('mismatched_keys') or info.get('error_msgs'):raise ValueError('Pesi EmbeddingGemma 2 incompleti: nessun parametro casuale ammesso.')
        self.model.to(device).eval()
        self.tokenizer=AutoTokenizer.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
        self.processor=AutoProcessor.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False) if self.visual else None
        emit('loaded',dimensions=DIMENSIONS,device=device)

    def encode(self,request):
        from h3chat.embeddinggemma2 import formatted,DIMENSIONS
        torch=self.torch;vectors=[];items=request.get('items')
        if items is None:items=[{'text':t} for t in request.get('texts',[])]
        if not isinstance(items,list) or not 1<=len(items)<=8 or any(not isinstance(t,dict) or not isinstance(t.get('text',''),str) or len(t.get('text',''))>100000 for t in items):raise ValueError('Richiesta embedding non valida.')
        for item in items:
            text=item.get('text','');image=item.get('image')
            if image:
                if not self.visual:raise ValueError('Indicizzazione immagini EmbeddingGemma 2 disattivata.')
                from PIL import Image
                Image.MAX_IMAGE_PIXELS=20_000_000;path=Path(image)
                if not path.is_absolute() or not path.is_file() or path.stat().st_size>32*1024**2:raise ValueError('Immagine embedding non valida.')
                with Image.open(path) as picture:
                    if picture.width*picture.height>20_000_000:raise ValueError('Immagine embedding troppo grande.')
                    inputs=self.processor(text=formatted(text[:1600],image=True),images=[picture.convert('RGB')],return_tensors='pt')
            else:
                inputs=self.tokenizer(formatted(text,bool(request.get('query'))),return_tensors='pt',truncation=True,max_length=2048)
            inputs=inputs.to(self.device)
            for name,value in inputs.items():
                if torch.is_tensor(value) and value.is_floating_point():inputs[name]=value.to(self.dtype)
            if inputs.input_ids.shape[-1]>8192:raise ValueError('Pagina troppo complessa per EmbeddingGemma 2.')
            with torch.inference_mode():
                hidden=self.model(**inputs,return_dict=True).last_hidden_state.float()
                mask=inputs.attention_mask.unsqueeze(-1).float()
                vector=(hidden*mask).sum(dim=1)/mask.sum(dim=1).clamp(min=1)
                if vector.shape[-1]!=DIMENSIONS or not torch.isfinite(vector).all() or (vector.norm(dim=-1)<=0).any():raise ValueError('EmbeddingGemma 2 ha prodotto un vettore non valido.')
                vectors.extend(torch.nn.functional.normalize(vector,p=2,dim=-1).cpu().tolist())
        emit('result',vectors=vectors)

if __name__=='__main__':
    emit('hello');worker=Worker()
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if request.get('op')=='load':worker.load(request)
            elif request.get('op')=='encode':worker.encode(request)
            else:raise ValueError('Operazione embedding non valida.')
        except Exception as error:traceback.print_exc();emit('error',message=str(error));break
