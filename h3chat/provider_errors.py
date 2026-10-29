"""Explain known rejected API parameters without persisting provider echoes."""
import json

def bad_request(raw):
    fallback='Richiesta o parametri non supportati: verifica modello, Vision, thinking e formato JSON.'
    try:
        value=json.loads(raw);error=value.get('error',{})
        if not isinstance(error,dict):return fallback
        message=error.get('message','');metadata=error.get('metadata',{})
        extra=metadata.get('raw','') if isinstance(metadata,dict) else ''
        content=(' '.join(x for x in (message,extra) if isinstance(x,str))).lower()[:16000]
        param=error.get('param','');param=param if isinstance(param,str) else ''
    except (ValueError,TypeError,AttributeError):return fallback
    if param in ('max_tokens','max_completion_tokens') or any(x in content for x in ('max_tokens','max_completion_tokens')) and any(x in content for x in ('maximum','at most','too large','exceed','less than','invalid')):
        return 'Il provider ha rifiutato il limite di token in uscita. Riduci Max token nelle impostazioni del modello API; il contesto è un limite distinto.'
    if param in ('reasoning','reasoning_effort','thinking') or any(x in content for x in ('reasoning','thinking')) and any(x in content for x in ('not support','unsupported','cannot','invalid','must be','required')):
        return 'Il provider ha rifiutato i parametri Thinking/Reasoning. Verifica la modalità Thinking della connessione e i livelli accettati dal modello.'
    if param in ('response_format','json_schema') or any(x in content for x in ('response_format','json_schema','json mode')) and any(x in content for x in ('not support','unsupported','invalid','must be')):
        return 'Il provider ha rifiutato il formato JSON richiesto. Scegli un formato compatibile nelle impostazioni della connessione API.'
    if any(x in content for x in ('image','vision','multimodal')) and any(x in content for x in ('not support','unsupported','invalid','cannot')):
        return 'Il provider ha rifiutato gli input immagine. Controlla il modello selezionato e l’abilitazione Vision nella connessione API.'
    if 'context' in content and any(x in content for x in ('exceed','too long','maximum')):
        return 'La richiesta supera il contesto accettato dal provider. Riduci fonti/allegati o il budget di risposta del modello.'
    return fallback
