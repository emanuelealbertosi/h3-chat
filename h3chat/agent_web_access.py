"""Run-scoped Web consent. Only human approval or its autoapprove policy grants it."""
import re,time

WEB_TOOLS={'web_search','read_web_page','search_web_images','import_web_images','import_web_sources','import_public_study_source','download_web_document',
           'download_web_file','install_lora_from_url','download_catalog_model','download_online_video','request_web_access'}

def required(name):return name in WEB_TOOLS or name.startswith('browser_')

def forbidden(request):
    return bool(re.search(r'\b(?:senza\s+(?:il\s+)?(?:web|internet|rete)|non\s+(?:usare|utilizzare|attivare|abilitare)\s+(?:il\s+)?(?:web|internet|rete)|(?:lavora|solo)\s+offline|do not (?:use|enable) (?:the )?(?:web|internet)|without (?:web|internet))\b',request,re.I))

def check(state):
    if forbidden(state['request']):raise PermissionError('La richiesta umana esclude Internet: Web non attivato.')
    if not state['config'].get('web_on_demand',True):raise PermissionError('Web è disattivato e la richiesta di accesso su necessità non è autorizzata nelle preferenze Agent.')

def grant(state,action,source):
    check(state)
    if source not in ('human_approval','autoapprove_policy'):raise PermissionError('Consenso Web non valido.')
    state['web_enabled']=True
    state.setdefault('web_grants',[]).append({'action_id':action['id'],'source':source,'at':time.time(),'scope':'this_run_only'})

def definitions():
    return {'request_web_access':('Chiedi di attivare Internet soltanto per questo lavoro quando serve. Con conferme attive apre una richiesta umana; con autoapprovazione autorizzata usa la policy salvata. Non modifica il Web globale, altri permessi, credenziali o scope. Non può ignorare una richiesta umana di lavorare senza Internet.',
        {'type':'object','properties':{'reason':{'type':'string','maxLength':1000}},'required':['reason'],'additionalProperties':False})}
