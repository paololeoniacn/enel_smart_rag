import chromadb
from sentence_transformers import SentenceTransformer
from config import config

class KnowledgeBase:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=config.chroma_persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=config.collection_name,
            
        )
        # Forza CPU per evitare OOM su GPU condivisa con il modello LLM
        self.embedder = SentenceTransformer(config.embedding_model, device="cpu")
    
    def add_documents(self, chunks: list[dict]):
        """
        chunks = [{"id": "doc1_chunk0", "text": "...", "metadata": {"source": "file.pdf", "page": 1}}]
        """
        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.encode(texts, normalize_embeddings=True).tolist()
        
        self.collection.add(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[c["metadata"] for c in chunks]
        )
    
    def search(self, query: str, n_results: int = None) -> list[dict]:
        n = n_results or config.max_retrieval_results
        query_embedding = self.embedder.encode([query], normalize_embeddings=True).tolist()
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n,
            include=["documents", "metadatas", "distances"]
        )
        
        output = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                distance = results["distances"][0][i]
                # Cosine distance → similarity: 0 = identico, 2 = opposto
                similarity = 1 - distance
                
                if similarity >= config.similarity_threshold:
                    output.append({
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": round(similarity, 4)
                    })
        
        return output
    
    def count(self) -> int:
        return self.collection.count()
