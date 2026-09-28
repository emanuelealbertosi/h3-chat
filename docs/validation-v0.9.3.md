# Verifiche H3-Chat 0.9.3

Include le correzioni e i collaudi descritti in validation-v0.9.2.md. La 0.9.2 non è stata pubblicata come release finale: l'audit delle dipendenze ha rilevato che llama.cpp e stable-diffusion.cpp richiedono il CRT Microsoft, disponibile sul PC di sviluppo ma non garantito su un nuovo Windows.

La 0.9.3 include le DLL x64 originali Microsoft 14.44.35112 con firme Authenticode valide e manifest SHA-256. Installer, download dal Setup e pacchetto portatile le collocano accanto ai motori CPU/CUDA/Vulkan. Non viene installato il redistributable nel sistema e non sono richiesti privilegi amministrativi. I test verificano la copia, l'integrità e la presenza delle dipendenze CRT; resta necessario Windows 10/11 x64, che fornisce Universal CRT.

110 test Python superati. Il probe nativo controlla anche, tramite le API Windows, che le DLL CRT caricate provengano dalla cartella del motore e non da Windows/System32. Reinstallazione del clone verificata con PATH limitato a Windows, senza download aggiuntivi e con i dati precedenti conservati.

La release finale 0.9.4 include questi stessi componenti e corregge il test per i percorsi Windows abbreviati (8.3), usati dal runner GitHub. Il comportamento del programma resta quello collaudato sopra.
