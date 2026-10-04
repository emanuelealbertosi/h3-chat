"""Ovis offline text/image retrieval; audio and generation towers stay unloaded."""
import json,logging,os,sys,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT/'runtime/vision'
dll_directory=os.add_dll_directory(str(RUNTIME/'dlls')) if os.name=='nt' and (RUNTIME/'dlls').is_dir() else None
sys.path[:0]=[str(ROOT),str(RUNTIME/'packages')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HOME=str(RUNTIME/'cache'))
wire=sys.stdout;sys.stdout=sys.stderr
logging.basicConfig(level=logging.WARNING,stream=sys.stderr)

def emit(event,**values):
    wire.write(json.dumps({'event':event,**values},ensure_ascii=False)+'\n');wire.flush()

class Worker:
    def load(self,request):
        import torch
        from transformers import AutoTokenizer,Qwen2_5OmniConfig,Qwen2_5OmniThinkerForConditionalGeneration
        from h3chat.ovis import checkpoint
        folder,_=checkpoint(request['path']);device=request['device']
        if device not in ('cpu','cuda'):raise ValueError('Dispositivo embedding non valido.')
        if device=='cuda' and not torch.cuda.is_available():raise ValueError('Ovis GPU richiede NVIDIA CUDA. Seleziona CPU nelle Preferenze.')
        torch.set_num_threads(max(1,min(int(request.get('threads',4)),16)))
        config=Qwen2_5OmniConfig.from_pretrained(str(folder),local_files_only=True)
        visual=bool(request.get('visual',False))
        # A meta-initialized identity removes the vocabulary projection from
        # loading and inference; output.logits is exactly the final hidden state.
        class RetrievalThinker(Qwen2_5OmniThinkerForConditionalGeneration):
            _tied_weights_keys={}
            _keys_to_ignore_on_load_unexpected=[r'^(?:thinker\.)?(?:audio_tower|lm_head)\.',r'^(?:talker|token2wav)\.']+([] if visual else [r'^(?:thinker\.)?visual\.'])
            def __init__(self,config):
                super().__init__(config)
                self.lm_head=torch.nn.Identity()
                self.audio_tower=torch.nn.Identity()
                if not visual:self.visual=torch.nn.Identity()
        emit('stage',message='RAG · caricamento Ovis · '+('GPU' if device=='cuda' else 'CPU'))
        dtype=(torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if device=='cuda' else torch.float32
        self.model,info=RetrievalThinker.from_pretrained(str(folder),config=config.thinker_config,
            dtype=dtype,
            attn_implementation='sdpa',local_files_only=True,use_safetensors=True,output_loading_info=True)
        if info.get('missing_keys') or info.get('mismatched_keys') or info.get('error_msgs'):
            raise ValueError('Pesi Ovis incompleti: impossibile usare parametri inizializzati casualmente.')
        self.model.to(device).eval();self.device=device;self.torch=torch
        self.tokenizer=AutoTokenizer.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
        self.tokenizer.chat_template=(folder/'chat_template.jinja').read_text(encoding='utf-8')
        self.visual=visual;self.processor=None
        if visual:
            from transformers import AutoProcessor
            self.processor=AutoProcessor.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False,use_fast=False)
            self.processor.chat_template=self.tokenizer.chat_template
        emit('loaded',dimensions=2048,device=device)
    def encode(self,request):
        from h3chat.ovis import messages
        torch=self.torch;vectors=[]
        items=request.get('items')
        if items is None:items=[{'text':t} for t in request.get('texts',[])]
        if not isinstance(items,list) or not 1<=len(items)<=8 or any(not isinstance(t,dict) or not isinstance(t.get('text',''),str) or len(t.get('text',''))>100000 for t in items):raise ValueError('Richiesta embedding non valida.')
        for item in items:
            text=item.get('text','');image=item.get('image')
            if image:
                if not self.visual:raise ValueError('Indicizzazione immagini Ovis disattivata.')
                from PIL import Image
                Image.MAX_IMAGE_PIXELS=20_000_000
                path=Path(image)
                if not path.is_absolute() or not path.is_file() or path.stat().st_size>32*1024**2:raise ValueError('Immagine embedding non valida.')
                with Image.open(path) as picture:
                    if picture.width*picture.height>20_000_000:raise ValueError('Immagine embedding troppo grande.')
                    formatted=self.processor.apply_chat_template(messages(text[:1600],False,str(path)),tokenize=False,add_generation_prompt=True)
                    inputs=self.processor(text=formatted,images=[picture.convert('RGB')],return_tensors='pt',images_kwargs={'min_pixels':3136,'max_pixels':602112}).to(self.device)
                if inputs.input_ids.shape[-1]>4096:raise ValueError('Pagina troppo complessa per Ovis: riduci il testo associato.')
            else:
                formatted=self.tokenizer.apply_chat_template(messages(text,bool(request.get('query'))),tokenize=False,add_generation_prompt=True)
                inputs=self.tokenizer(formatted,return_tensors='pt',truncation=True,max_length=2048).to(self.device)
            with torch.inference_mode():
                hidden=self.model(**inputs,use_cache=False,return_dict=True).logits
                positions=torch.arange(inputs.attention_mask.shape[-1],device=hidden.device)
                last=positions.masked_fill(~inputs.attention_mask.bool(),-1).max(dim=-1).values
                vector=hidden[torch.arange(hidden.shape[0],device=hidden.device),last].float()
                if vector.shape[-1]!=2048 or not torch.isfinite(vector).all() or (vector.norm(dim=-1)<=0).any():raise ValueError('Embedding Ovis non valido.')
                vectors.extend(torch.nn.functional.normalize(vector,p=2,dim=-1).cpu().tolist())
        emit('result',vectors=vectors)

emit('hello');worker=Worker()
for line in sys.stdin:
    try:
        request=json.loads(line)
        if request.get('op')=='load':worker.load(request)
        elif request.get('op')=='encode':worker.encode(request)
        else:raise ValueError('Operazione embedding non valida.')
    except Exception as error:
        traceback.print_exc();emit('error',message=str(error));break
