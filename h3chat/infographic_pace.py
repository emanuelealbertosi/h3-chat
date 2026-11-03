"""Opt-in rapid explanatory direction; never time-warps an existing voice."""
def brief(opts):
    if opts.get('pace')!='explainer':return ''
    return ('\nRITMO RAPIDO · EXPLAINER: frasi brevi, una sola informazione per battuta. Organizza ogni scena in accenti visivi ogni 2–4 secondi: ingresso del concetto, dettaglio, collegamento al successivo. '
      'Alterna campo d’insieme e primi piani di oggetti, zoom dolci sugli sfondi e piccoli spostamenti; non far tremare la camera né zoomare le scritte HUD. '
      'Mantieni pochi testi visibili e leggibili, sequenziali, senza muri di parole. Progetta la fine e l’inizio delle scene vicine con stessa direzione di movimento, palette ed elemento di raccordo. '
      'Usa i gesti dei personaggi per accompagnare il punto spiegato, non un movimento continuo casuale. La voce non viene accelerata artificialmente: ottieni ritmo da scrittura concisa, recitazione partecipe e montaggio. '
      'Rispetta durata reale della voce, prompt, allegati e fonti; non aggiungere fatti per riempire il video.')
