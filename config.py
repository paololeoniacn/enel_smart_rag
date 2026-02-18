from pydantic import BaseModel

class Config(BaseModel):
    # Modello
    # model_name: str = "qwen3:30b-a3b"  # 30B (Pesante)
    # model_name: str = "deepseek-r1:14b" # Reasoning (Troppo verboso)
    model_name: str = "qwen2.5:14b"      # 14B (Bilanciato per Mac 24GB)
    ollama_base_url: str = "http://localhost:11434"
    
    # Embedding
    embedding_model: str = "intfloat/multilingual-e5-small"
    
    # ChromaDB
    chroma_persist_dir: str = "./chroma_store"
    collection_name: str = "knowledge_base"
    
    # Retrieval
    max_retrieval_results: int = 10
    max_retrieval_retries: int = 3
    similarity_threshold: float = 0.35
    
    # Chunking
    chunk_size: int = 1024
    chunk_overlap: int = 128
    
    # Generazione
    temperature: float = 0.3
    num_ctx: int = 4096
    max_tokens: int = 4096

config = Config()
