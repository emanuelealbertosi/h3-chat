import argparse,hashlib,json,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from h3chat.service import Service
from h3chat.loras import for_model
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Real Anima Turbo CPU test; requires the pinned model components and official aesthetic boost LoRA.')
parser.add_argument('--weights',type=Path,required=True);parser.add_argument('--data',type=Path,default=root/'work/real-anima-test')
args=parser.parse_args();weights=args.weights.resolve();out=args.data.resolve()
assert out!=root/'data','Use separate test data, not personal conversations'
names={'diffusion':'anima-turbo-v1.1-Q4_K_M.gguf','llm':'Qwen3-0.6B-Base.Q4_K_M.gguf','vae':'qwen_image_vae.safetensors'}
app=Service(root,out,start_worker=False)
try:
    model=app.external_model({'profile':'anima-turbo','name':'Anima Turbo 1.1 Q4 real test','files':{k:str(weights/v) for k,v in names.items()}})
    assert model['ready'],model
    dirs=[str(weights)];items=app.loras.scan(dirs)['items'];items=[i for i in items if i['filename']=='anima-highres-aesthetic-boost.safetensors'];assert len(items)==1,items
    selection=app.loras.capture([{'id':items[0]['id'],'model_id':model['id'],'weight':1}],dirs,app.catalog)
    settings=app.save_settings({'profile':'cpu','backend':'cpu','threads':6,'memory_policy':'on_demand','ram_cache_gb':0,
                               'create_model':model['id'],'width':512,'height':512,'seed':123456,'lora_dirs':dirs})
    originals={p.name:hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in (weights/name for name in [*names.values(),items[0]['filename']])}
    results=[];cancel=threading.Event();prompt='A colorful storybook illustration of a small red-roofed cottage beside a clear pond, surrounded by flowers and tall green trees. Soft sunlight illuminates the garden, with a blue sky in the background. Safe, peaceful landscape, no people.'
    for label,loras in [('baseline',[]),('with-lora',selection),('removed-lora',[])]:
        started=time.monotonic();print('START',label,flush=True)
        def stage(text):print(label,text,flush=True)
        media=app.engine.generate(model,settings|{'_loras':for_model(loras,model)},prompt,[],label,cancel,stage)
        path=out/media['path'];snapshot=app.engine.snapshot()
        result={'label':label,'seconds':round(time.monotonic()-started,2),'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),'path':str(path),'generation':media['generation'],'memory':snapshot}
        results.append(result);print('RESULT',json.dumps(result),flush=True)
    assert results[0]['sha256']!=results[1]['sha256'],'LoRA did not change the output'
    assert results[0]['sha256']==results[2]['sha256'],'LoRA was not completely removed'
    assert len(app.engine.sessions)==1 and next(iter(app.engine.sessions.values())).uses==3
    assert all(hashlib.file_digest((weights/name).open('rb'),'sha256').hexdigest()==value for name,value in originals.items())
    (out/'result.json').write_text(json.dumps({'passed':True,'backend':'cpu','resolution':[512,512],'steps':8,'results':results,'originals_unchanged':True,'one_context_three_generations':True},indent=2),encoding='utf-8')
    print('REAL ANIMA + LORA ADD/REMOVE OK',flush=True)
finally:app.close()
