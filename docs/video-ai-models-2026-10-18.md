# Modelli citati nel video AI Search del 18 ottobre

Nota del 21 ottobre: la funzione di ricostruzione 3D e i modelli locali
UniForge/Hunyuan/Paint sono stati rimossi. La sezione seguente conserva la
valutazione storica; non descrive una funzione attualmente disponibile nell'app.

Video richiesto: https://www.youtube.com/watch?v=tDWtcyeNNew
Identificati dalla descrizione ufficiale YouTube, verificati sui progetti degli autori. Non è stata rivendicata una visione integrale del filmato.

## UniForge3D — 05:06

È il candidato più pertinente per il problema della forma che non regge la rotazione. Usa viste sparse non calibrate per ricostruire geometria osservata e completare quella nascosta, selezionando le viste per regione. Nel nostro Hunyuan3D 2.1 solo il fronte determina la forma; gli altri riferimenti colorano la superficie.

Codice e pesi sono pubblici, anche se il sito della presentazione mostra ancora un link Code inattivo. Verificati:

- https://github.com/xibushu/UniForge3D
- https://huggingface.co/xibushu/UniForge3D
- https://xishuxishu.github.io/uniforge3d-project/
- https://arxiv.org/abs/2610.15357

Codice ispezionato alla revisione `8b6094780e202b8a6b1d239e0997552e18547026`. I checkpoint `.pt` del repository principale totalizzano circa **25,08 GiB**; l'intero repository con immagini/config è circa 25,11 GiB. Sono richiesti anche pesi esterni TRELLIS/TRELLIS.2, DINOv3 e il rimuovi-sfondo: il fabbisogno disco reale è maggiore. Lo script ufficiale carica entrambe le fasi shape512 e shape1024 e poi le texture, quindi togliere semplicemente i pesi 1024 non conserva la pipeline ufficiale.

Esiste un offload per fasi `low_vram=True`: i moduli vengono portati su CUDA e poi riportati in CPU. Non è una misura di consumo sulla nostra RTX 5070 Ti da 16 GB. Nessun benchmark locale è stato eseguito. L'installazione ufficiale usa Bash/Conda, Torch 2.6 cu124, Flash Attention e compilazione di nvdiffrast, CuMesh, FlexGEMM e o-voxel. Servono un ambiente separato e verifica delle build per Windows/Blackwell; non va eseguito alla cieca sul runtime video esistente.

Al controllo F: ha circa 2,2 GiB liberi, D: 7,8 GiB: insufficienti. Non sono stati scaricati pesi né installate dipendenze. I piccoli sorgenti e la lista dimensioni sono in `work/model-video-research-2026-10-18/`.

Il codice originale è MIT; il README distingue i termini dei checkpoint VGGT e RMBG. La prova va valutata con le tre viste omogenee dello stesso soggetto, non mescolando Cass e la tavola bionda. Un miglior risultato è plausibile, non ancora dimostrato.

## GaussiAnimate — 03:53

https://github.com/Net-Maker/GaussiAnimate
https://cookmaker.cn/gaussianimate/

Il codice è pubblicato. Non anima automaticamente un GLB statico da un singolo prompt: l'ingresso principale è una sequenza 3D registrata nel tempo, con gli stessi punti materiali nello stesso ordine. Da questa estrae scheletro e ossa esterne, poi usa PartMM per nuove pose. Per i nostri GLB statici manca prima una fase di rig/animazione coerente; non è un sostituto diretto di Hunyuan.

## MOSS-Image-SFT — 20:47

SFT significa *supervised fine-tuning*: è una variante addestrata ulteriormente del modello immagini MOSS, non un motore 3D. Supporta testo naturale e layout JSON sperimentali.

https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT
https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md#layout-prompts-experimental

Il formato ufficiale usa `summary.caption`, `items`, `bbox_format: yxyx` e `bbox_coord_space: abs_centralized`: coordinate pixel con origine al centro. La traduzione Assistant in chat produce una bozza normalizzata e l'app la converte in modo deterministico usando le dimensioni finali richieste. Non richiede nuovi pesi. Vedi `docs/moss-image.md` per l'uso.
