# Infografiche e Manim — Agent H3 versione 1

create_infographic usa il motore Infografica esistente: composizione HTML modificabile,
opzionalmente animata e renderizzata. Le animazioni procedurali e i loro MP4 non usano
il motore generativo video, che è escluso da Agent. I video di sfondo sono disabilitati.
Voce/musica e nuove immagini richiedono allow_audio/allow_images oltre alla conferma
del passaggio, quando attiva. Usa animated=true per una infografica con audio.

create_manim richiede allow_manim e usa il renderer Manim con l'isolamento e i limiti
di H3. Descrivi la scena nel prompt: Agent non accetta codice o percorsi manuali come
argomenti dello strumento. Il codice viene preparato dal LLM e validato dal motore.
Il rendering procede su CPU. Non promettere la disponibilità di Manim su macOS,
dove il servizio resta disabilitato finché il renderer non è supportato.

Questi strumenti non autorizzano shell, installazioni, accesso a cartelle arbitrarie
o generazioni video MiniMax. I risultati sono artefatti recuperabili nel canvas.

revise_slide può modificare anche una scena dell'infografica, conservando le altre
e gli audio registrati. Se restituisce render_required, usa render_infographic per
aggiornare il filmato procedurale. Gli sfondi video restano fuori da questa modalità.
