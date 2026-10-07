"""Supported native multimodal RAG profiles."""
def visual_enabled(settings):
    return settings.get('rag_embedding_profile') in ('ovis','embeddinggemma2') and bool(settings.get('rag_embedding_model')) and settings.get('rag_visual',True)
