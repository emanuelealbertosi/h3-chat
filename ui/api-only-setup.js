// This is a settings shortcut, not a separate runtime or a GPU feature lock.
export function apiOnlySettings(draft,models){
 const patch={profile:'cpu',backend:'cpu',gpu_layers:0,llm_device:'cpu',image_device:'cpu',rag_device:'cpu',asr_device:'cpu',vision_device:'cpu',music_backend:'cpu',music_quality:'model',llm_acceleration:'standard',mtp_enabled:false,memory_policy:'on_demand',ram_cache_gb:0,transcribe_auto:false,voice_auto:false,diagram_model:''};
 for(const [field,capability] of [['chat_model','chat'],['create_model','create'],['edit_model','edit'],['music_model','music'],['video_model','video']]){
  const candidates=models.filter(model=>model.ready&&(capability==='chat'?model.api:model.remote_media)&&model.capabilities?.includes(capability));
  patch[field]=candidates.find(model=>model.id===draft[field])?.id||candidates[0]?.id||'';
 }
 return patch;
}

export const apiOnlyCard=`<section class="card api-only-setup"><h3>Usa API · anche senza GPU</h3><p>Chat, Assistant, slide e infografiche possono usare un LLM esterno. Immagini, musica e video usano i server configurati. Il RAG resta locale su CPU; puoi scegliere un embedding leggero nelle Preferenze.</p><p class="small-note">Non servono pesi generativi locali o motori GPU. Trascrizione e voce locale restano funzioni opzionali da installare separatamente. Il pulsante conserva i collegamenti API disponibili e deseleziona i modelli generativi locali, senza cancellarli.</p><button type="button" id="setup-api-only" class="btn">Configura per API · nessuna GPU</button> <button type="button" id="setup-api-providers" class="text-button">Collega provider e server →</button></section>`;
