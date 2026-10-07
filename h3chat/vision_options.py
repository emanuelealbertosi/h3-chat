"""Per-LLM Vision reference budget; API provider capacity remains authoritative."""
DEFAULT_MAX_REFS=4
MAX_REFS=12


def reference_limit(model,settings):
    requested=settings.get('vision_max_refs',DEFAULT_MAX_REFS)
    if type(requested) is not int or not 1<=requested<=MAX_REFS:
        raise ValueError(f'Immagini Vision per richiesta: inserisci un intero tra 1 e {MAX_REFS}.')
    if model.get('api'):
        capacity=model.get('max_refs',model.get('vision',{}).get('max_refs',DEFAULT_MAX_REFS))
        return min(requested,capacity)
    return requested
