# Infografiche e Manim — Agent H3 versione 1

create_infographic usa il motore Infografica esistente: composizione HTML modificabile,
opzionalmente animata e renderizzata. Le animazioni procedurali e i loro MP4 non usano
il motore generativo video. Per i filmati MiniMax usa gli strumenti separati e la
skill video, con allow_video. I video di sfondo Infografica sono disabilitati.
Voce/musica e nuove immagini richiedono allow_audio/allow_images oltre alla conferma
del passaggio, quando attiva. Usa animated=true per una infografica con audio.

create_manim richiede allow_manim e usa il renderer Manim con l'isolamento e i limiti
di H3. Descrivi la scena nel prompt: Agent non accetta codice o percorsi manuali come
argomenti dello strumento. Il codice viene preparato dal LLM e validato dal motore.
Il rendering procede su CPU, con un renderer isolato anche nel pacchetto macOS.
Verifica che il runtime locale sia pronto prima di promettere un risultato.

Questi strumenti non autorizzano shell, installazioni, accesso a cartelle arbitrarie
o generazioni video MiniMax. I risultati sono artefatti recuperabili nel canvas.

revise_slide può modificare anche una scena dell'infografica, conservando le altre
e gli audio registrati. Se restituisce render_required, usa render_infographic per
aggiornare il filmato procedurale. Gli sfondi video restano fuori da questa modalità.
