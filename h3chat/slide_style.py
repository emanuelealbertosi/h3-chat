"""Shared art direction for LLM-authored pages and their generated illustrations."""

GUIDES = {
    'professional': '''STILE VISIVO: serio / professionale.
Direzione editoriale sobria: palette misurata con neutri e pochi accenti cromatici,
allineamenti precisi, spazio bianco generoso, gerarchia tipografica netta.
Scegli caratteri eleganti e leggibili; usa pesi e dimensioni per distinguere i livelli.
Composizioni ordinate ma varie, grafici essenziali, forme geometriche pulite.
Illustrazioni: trattamento editoriale raffinato, colori controllati, dettagli
pertinenti e atmosfera credibile; evita mascotte buffe, sticker e balloon comici.''',
    'playful': '''STILE VISIVO: giocoso / colorato.
Deve essere riconoscibile visivamente, non solo nel tono del testo: palette vivace
con più colori coordinati e accenti contrastanti, forme morbide o organiche,
tipografia amichevole con titoli espressivi e testo ben leggibile.
Composizioni dinamiche e asimmetrie controllate, ritmo tra dimensioni e pieni/vuoti,
piccoli elementi illustrativi o sticker pertinenti, senza ripetere sempre le stesse card.
Illustrazioni: immaginative, energiche, colori vivaci, forme espressive e un tono
ludico; non riutilizzare l'aspetto sobrio di un deck aziendale cambiando solo un accento.
Conserva precisione dei contenuti: giocoso non significa banalizzare o inventare fatti.''',
    'comic': '''STILE VISIVO: fumettoso.
Direzione da fumetto illustrato: contorni a inchiostro, contrasti netti, campiture
colorate, pannelli e didascalie espressive, balloon quando utili al contenuto.
Usa segni di movimento, retini o piccoli accenti grafici con misura; titoli incisivi,
testo di lettura chiaro. Varia la composizione, senza rinchiudere tutto in vignette identiche.
Illustrazioni: disegno da fumetto con line art visibile, campiture e ombre grafiche,
personaggi o metafore pertinenti; niente testo incorporato nell'immagine.
Deve distinguersi sia dalla grafica aziendale sia dalle sole forme morbide del giocoso.''',
}

COMMON = '''Scegli TU palette concreta, font e layout adatti all'argomento, entro questa
direzione: nessun template obbligatorio. Descrivi in visual_direction colori,
gerarchie tipografiche, forme, composizione e trattamento delle illustrazioni;
applicali poi nell'HTML e nei prompt immagini, non solo nei titoli.
Lo stile selezionato per questa richiesta prevale sulle direzioni artistiche
di presentazioni precedenti nella cronologia: non copiarne automaticamente l'aspetto.
Preferenze esplicite dell'utente su palette, caratteri o tecnica delle immagini
(es. fotografie) vanno rispettate e declinate nello stile scelto. Il tema del
contenuto da solo non cambia lo stile. Testi completi, fonti e contrasto leggibile
restano obbligatori in ogni stile. Immagini caricate o provenienti dal RAG sono
fonti originali: non ridisegnarle per adattarle allo stile.'''

IMAGE_CUES = {
    'professional': 'professional editorial visual style, restrained coordinated colors, clean refined composition',
    'playful': 'playful visual style, vibrant coordinated colors, expressive shapes, lively imaginative composition',
    'comic': 'comic book visual style, ink outlines, graphic shading, bold color blocks, expressive composition',
}


def brief(design):
    return GUIDES.get(design, GUIDES['professional']) + '\n' + COMMON


def image_prompt(prompt, design, form):
    # Keep the subject/medium authored by the LLM, but do not lose the selected
    # style when an image planner returns a generic prompt. No extra model call.
    cues = IMAGE_CUES.get(design, IMAGE_CUES['professional'])
    if form == 'tags':
        return prompt.rstrip(' ,.') + ', ' + cues
    return prompt.rstrip() + '\nVisual direction: ' + cues + '.'
