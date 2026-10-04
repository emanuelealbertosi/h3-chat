"""Separate chat attachments from whole-book project indexing."""
RAG_FILE_BYTES=512*1024**2
RAG_PDF_PAGES=3000
RAG_TEXT_CHARS=10_000_000
RAG_CHUNKS=20_000
IMPORT_CHUNK_BYTES=2*1024**2
INLINE_IMPORT_BYTES=25*1024**2
RAG_LIMITS={'file_bytes':RAG_FILE_BYTES,'pdf_pages':RAG_PDF_PAGES,
            'text_chars':RAG_TEXT_CHARS,'upload_chunk_bytes':IMPORT_CHUNK_BYTES}

def limits(profile):
    if profile=='rag':return RAG_PDF_PAGES,RAG_TEXT_CHARS,512*1024**2
    if profile=='chat':return 300,2_000_000,100*1024**2
    raise ValueError('Profilo di lettura documento non valido.')
