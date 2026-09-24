"""Deterministic image selection and the local LLM's visual briefing contract."""
import re

VISUAL_BRIEF = '''You prepare precise, self-contained instructions for Ming Image or Qwen Image 2.1.
Return JSON with exactly one field, "prompt". No analysis or commentary.
Write the generation instructions in English. Keep all visible labels in the user's
requested language (otherwise use the language of the request). Preserve quoted
wording, names, numbers, formulas, units and reference-image numbering exactly.
Describe composition, objects, layout, style, colours, lighting and legibility as
appropriate to the request. Do not turn ordinary photographs into infographics.
For graphs/diagrams specify every entity, edge, arrow direction and relationship.
For mathematical plots specify functions, axes, ranges, domain, notable points,
curvature and discontinuities. Check equations and label placement for consistency.
Use only supplied data. Do not invent measurements, sources, research or citations.
When data are absent, request an explicitly illustrative schematic, never fabricated
measurements presented as facts. Keep visual text short and legible; preserve any
longer text the user explicitly requires. Aim for 250–450 words of instructions.
For edits describe what to change and preserve, referencing image 1, image 2, etc.
If images are not included as vision input, you have not seen them: describe only
the user's instructions and do not invent their contents. Image generation itself
receives the original references. Conversation context helps interpret follow-ups;
the latest user request has precedence. Never claim the result is mathematically
verified; the image model can still make mistakes in lettering or geometry.'''


def visual_route(history, settings):
    """Explicit selection wins; auto-Ming is restricted to requests to MAKE visuals.

    Structured/exact output stays with the existing data/chart/Mermaid renderer.
    Mere discussion, explanations and negations do not invoke a diffusion model.
    """
    original = history[-1]['content']
    text = original.casefold().strip()
    current_refs = bool(history[-1].get('media'))
    available_refs = any(m.get('media') for m in history)
    edit = current_refs or (available_refs and bool(re.match(r'^(?:modifica|correggi|cambia|ritocca|edit|change)\b', text)))
    explicit = settings.get('_image_model', '')
    if explicit:
        return {'intent':'edit' if edit else 'create', 'prompt':original, 'image_model':explicit, 'selection':'explicit'}
    if not settings.get('diagram_model') or not settings.get('diagram_auto', True):
        return None
    if re.search(r'\b(?:mermaid|chart\.js|json|svg|python|matplotlib|interattiv[oaie]|dati esatti|grafico esatto|codice|senza (?:generare|immagini))\b', text):
        return None
    opening = re.sub(r'^(?:(?:per favore[, ]*|puoi\s+|potresti\s+|vorrei\s+|mi piacerebbe\s+|please\s+|can you\s+))+', '', text)
    if not re.match(r'^(?:crea(?:mi)?|creare|genera(?:mi)?|generare|disegna(?:mi)?|disegnare|realizza|realizzare|fammi|fai|mostra(?:mi)?|ricostruisci|ridisegna|modifica|correggi|create|generate|draw|make|redraw|edit)\b', opening):
        return None
    if re.search(r'\b(?:grafico|grafici|grafo|grafi|diagramm[ai]|infografic[aohe]+|schem[ai]|mapp[ae] concettual[ei]|chart|graph|diagram|infographic|flowchart)\b', opening[:250]):
        return {'intent':'edit' if edit or (available_refs and opening.startswith(('ricostruisci','ridisegna'))) else 'create',
                'prompt':original, 'image_model':settings['diagram_model'], 'selection':'diagram'}
    return None
