# MTP e limite di risposta

Dal pulsante accanto a Think in chat, oppure da **Impostazioni → Preferenze**, puoi impostare:

- **Max token di risposta**: 64–8192 token, fino a metà del contesto. Comprende testo e thinking, anche per il canvas. Il valore precedente viene conservato negli aggiornamenti; per una nuova installazione è 1024.
- **Attiva MTP per i modelli compatibili**: disattivato inizialmente. L'opzione è disponibile solo quando il GGUF installato contiene i moduli necessari e l'architettura è supportata.
- **Token da anticipare**: 1–8, inizialmente 3. Il motore verifica le proposte prima di accettarle; aumentare questo numero non garantisce maggiore velocità. I modelli con più teste concatenate hanno anche il limite imposto dal numero di teste.

Le impostazioni vengono salvate sul computer e copiate nel lavoro al momento dell'invio. Cambiare MTP o il numero effettivo di token anticipati ricarica il modello dal prossimo lavoro; cambiare max token o Think non richiede un ricaricamento. Se scegli un modello senza MTP, la preferenza resta salvata ma la funzione resta disattivata e in chat compare **MTP N/D**.

Il limite max token riguarda l'output: **Contesto** regola invece lo spazio complessivo per istruzioni, cronologia, immagini e risposta. Il router interno ha un budget separato di 768 token.

## Rilevamento e motore

H3-Chat usa il MTP nativo di llama.cpp **b10809**: `--spec-type draft-mtp --spec-draft-n-max N`. Non scarica un secondo modello draft e non duplica i pesi: il contesto MTP condivide il modello principale. MTP disattivato viene inviato esplicitamente come `--spec-type none`.

Il rilevamento legge le intestazioni GGUF, senza caricare i pesi in memoria. Controlla `general.architecture`, `ARCH.nextn_predict_layers`, `ARCH.block_count`, i tensori principali e i tensori `nextn.eh_proj`, `nextn.enorm`, `nextn.hnorm` di tutti i moduli dichiarati, riunendo i file shard collegati. Il nome del file e i soli metadati NextN non bastano. I GGUF senza tensori MTP, con parti mancanti o contenenti solo una testa separata non abilitano l'opzione. Sono supportati i moduli incorporati nel GGUF completo; un draft MTP separato richiederebbe un collegamento aggiuntivo, non previsto da questa versione.

Le architetture riconosciute sono qwen35, qwen35moe, qwen3next, deepseek2, deepseek4, glm4moe, glm-dsa, nemotron_h_moe, step35 e hy_v3, con i limiti dei rispettivi grafi MTP del motore incluso. Il caricamento nativo rimane la verifica finale della compatibilità e dell'integrità dei pesi. Dopo l'avvio H3-Chat interroga `/slots`, autenticato sulla porta locale privata, e procede solo se il motore conferma la speculazione attiva. In caso contrario mostra un errore esplicito con l'indicazione di disattivare MTP.

La stima di RAM/VRAM include un margine per contesto, cache KV e lavoro MTP aggiuntivi. È una stima prudente, non una misurazione del picco; i pesi dei moduli presenti nel file erano già compresi nella stima del modello. Le prestazioni dipendono da modello, hardware, quantizzazione e percentuale di token accettati.

Fonti del motore incluso: [opzioni di decodifica speculativa](https://github.com/ggml-org/llama.cpp/blob/b10809/docs/speculative.md), [contesto MTP e condivisione dei pesi](https://github.com/ggml-org/llama.cpp/blob/b10809/common/speculative.cpp), [grafo Qwen3.5](https://github.com/ggml-org/llama.cpp/blob/b10809/src/models/qwen35.cpp), [verifica di speculazione negli slot del server](https://github.com/ggml-org/llama.cpp/blob/b10809/tools/server/server-context.cpp).
