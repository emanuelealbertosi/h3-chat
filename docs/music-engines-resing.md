# Motori musicali e Re-sing nella chat

Attiva **Music**, poi apri **Impostazioni Music**. La scelta del motore vale per
questa conversazione e resta salvata. I pesi vengono collegati dove sono già
installati: non vengono duplicati e non si avvia un server ComfyUI.

* **YuE2:** stile, testo, spartito ABC facoltativo, pianificazione, passi, CFG e seed.
* **MiniMax Music 3:** descrizione musicale/caption, testo, seed, durata massima,
  CFG e top K dell'encoder musicale, passi, CFG, sampler e scheduler della sintesi.
  Il limite predefinito è 120 secondi, configurabile fino a 360 secondi. Il modello
  può terminare prima. Non riceve spartiti ABC o un audio guida con questa modalità.

Anche le Preferenze generali mostrano i parametri del modello selezionato. I preset
della chat hanno la priorità; cambiando modello si recupera il suo preset, senza
trasferire parametri incompatibili dall'altro motore. Alta/Bassa restano disponibili
quando si usa la scelta musicale predefinita.

## Testo automatico

Con **Assistant On** o **Agente**, il testo del brano è facoltativo: descrivi il
tema e l'LLM scrive le parole prima di passarle al motore musicale. Non è YuE2
stesso a improvvisare il testo. Le parole già compilate nelle impostazioni
vengono conservate. Per una base senza canto scegli **Strumentale**.

Con **Assistant Off**, nella normale creazione Music, si passa direttamente al
motore: occorre fornire il testo nelle impostazioni o dopo `Testo:` nel messaggio,
oppure scegliere Strumentale. L'eccezione Re-sing senza testo è descritta sotto.

## Ricantare sulla base originale

1. Seleziona un **YuE2 locale** nelle impostazioni Music.
2. Allega una sola canzone audio, lunga da 3 secondi a 5 minuti.
3. Attiva **Re-sing**, accanto al pulsante Impostazioni Music.
4. Scrivi il nuovo testo nel campo **Testo del brano**: ha la priorità sul prompt.
   Se il campo è vuoto, Assistant inventa il nuovo testo seguendo il prompt, anche
   con Assistant Off. Per esempio: «Ricantala in italiano, parla di un viaggio».
   Le istruzioni non vengono usate come parole da cantare. Per questa scrittura
   automatica occorre un modello di chat configurato; con un testo già compilato
   e Assistant Off si passa direttamente alla generazione musicale.
5. Premi Invia. Il risultato è un nuovo WAV, in chat o nel canvas secondo la
   destinazione scelta. L'allegato originale resta intatto.

Re-sing usa la procedura già integrata da H3-Music: separazione HTDemucs, lettura
della melodia con SheetSage2/MERT, generazione YuE2 con ABC, separazione del nuovo
canto, controllo/allineamento dei tempi e mix sulla base originale. Il processo
mostra le fasi nella chat e rispetta Stop. Non taglia automaticamente canzoni più
lunghe e non pubblica un mix quando i controlli di allineamento falliscono.
In Re-sing un eventuale ABC salvato nelle impostazioni viene ignorato: melodia e
controlli dei tempi derivano sempre dalla canzone allegata. Si controllano ritardi,
frasi mancanti e piccoli scostamenti di tempo; le correzioni mantengono l'intonazione
e non modificano i tempi della base. Dopo una correzione si verifica il canto sulla
base e, se il riconoscimento del mix è ambiguo, anche la nuova voce isolata.
La qualità del canto e della separazione va comunque valutata ascoltando il brano.

MiniMax Music 3 resta un'alternativa per generare nuovi brani; Re-sing sulla melodia
originale è disabilitato con questo motore, perché la procedura richiede ABC.
Separazione e lettura spartiti devono risultare pronte in **Setup → Remix audio**.
I modelli già configurati per Remix vengono riutilizzati dagli stessi percorsi.
