# Video e timeline per Agent

Richiedono il permesso separato allow_video. Le altre modalità H3 e Assistant
restano disponibili. La modalità CPU dell'app disabilita il permesso video.

Usa list_models per gli ID reali e list_video_timelines per i lavori della chat.
inspect_video_timeline restituisce clip, prompt, memoria e versioni: sono metadati,
non una visione del filmato o un ascolto dell'audio.

create_video usa il normale motore Video. reference_numbers sceglie le immagini,
gli audio e i video espliciti tra gli allegati numerati, includendo i risultati
collegati con source_artifact_ids. Senza numeri non allega nulla. Mantieni i LoRA
video scelti dall'utente; non cambiare i preset globali. Assistant è spento di
default, ma può essere richiesto per la pianificazione. Questa pianificazione
segue i normali limiti del lavoro video, separati dal budget decisionale Agent.

parameters supporta formato, durata del clip, MP, seed e numero/modalità varianti.
variants_mode=clip crea più versioni per clip; video crea versioni complete.
Per un filmato musicale lungo allega l'audio scelto e lascia che H3 segua la sua
durata. Per storyboard diretto usa la sintassi H3 oppure Assistant On.

edit_video richiama l'editor, con source della stessa chat e patches numerati da 1.
Non accorcia le clip se non espressamente previsto dal normale editor. mode=video
modifica il girato; reference rigenera con riferimenti; i2v parte da un'immagine.
recover_memory e end_frame=original/next recuperano le guide autorizzate. Per
un'immagine finale già disponibile usa end_image con l'indice restituito dalla
timeline. Le guide non garantiscono identità, movimenti o labiale perfetti.

assemble_video monta la timeline con le versioni esplicitamente scelte; non usa
il generatore. resume_video completa solo le parti mancanti e va usato soltanto
quando l'utente chiede di riprendere. Uno Stop o un errore non autorizza rilanci.

Il rendering ha un vero ticket nella coda H3. Agent attende senza tenere caricato
il LLM e senza consumare il tempo attivo del coordinatore. Al risultato riprende
con gli stessi permessi e budget; al fallimento o Stop si ferma conservando clip.
Massimo 8 lavori video per sessione. Le scritture passano dalla conferma Agent
se abilitata. Un invio incerto si riconcilia per ID esatto, senza ripeterlo.
