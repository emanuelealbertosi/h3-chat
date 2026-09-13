import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from h3chat.service import Service
from test_loras_image_options import safetensors,lora
root=Path(__file__).resolve().parents[1];data=root/'work/qa-v06-data';fixtures=root/'work/qa-v06-fixtures'
app=Service(root,data,start_worker=False)
files={role:str(safetensors(fixtures/(role+'.safetensors'))) for role in ('diffusion','llm','vae')}
anima=app.external_model({'profile':'anima-turbo','name':'Anima Turbo · prova interfaccia','files':files})
flux=app.external_model({'profile':'flux2','name':'FLUX · prova interfaccia','files':files})
dirs=[str(fixtures/'Lora A'),str(fixtures/'Lora B')]
lora(Path(dirs[0])/'paesaggio.safetensors');lora(Path(dirs[1])/'dettagli.safetensors');lora(Path(dirs[1])/'flux style.safetensors','flux2')
app.save_settings({'profile':'cpu','backend':'cpu','chat_model':'qwen3-06','create_model':anima['id'],'edit_model':flux['id'],'setup_done':True})
chat=app.store.create_chat('Parametri immagine · esempio')
jid=app.store.enqueue(chat['id'],'Crea una immagine di una casa',[],app.store.settings())
job=app.store.one('SELECT * FROM jobs WHERE id=?',(jid,))
app.store.update_answer(job,'Ecco l’immagine.','done',[],{'intent':'create','model':anima['name'],'image_parameters':{'width':512,'height':512,'steps':8,'cfg':1,'sampler':'euler','scheduler':'discrete','seed':12345,'strength':.65,'negative_prompt':'sfocato'},'loras':[]})
app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(jid,));app.close()
(root/'work/qa-v06-config.json').write_text(json.dumps({'anima':anima['id'],'flux':flux['id'],'dirs':dirs,'chat':chat['id']}),encoding='utf-8')
print('QA fixture pronta',flush=True)
