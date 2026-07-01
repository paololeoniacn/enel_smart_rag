import re
import chromadb
from sentence_transformers import SentenceTransformer
from config import config


class KnowledgeBase:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=config.chroma_persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        # Forza CPU per evitare OOM su GPU condivisa con il modello LLM
        self.embedder = SentenceTransformer(config.embedding_model, device="cpu")
    
    def reset(self):
        """Cancella e ricrea la collection per una re-indicizzazione pulita."""
        self.client.delete_collection(config.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        print("🗑️  Collection resettata.")

    def add_documents(self, chunks: list[dict]):
        """
        chunks = [{"id": "doc1_chunk0", "text": "...", "metadata": {"source": "file.pdf", "page": 1}}]
        Usa il prefisso 'passage: ' per il modello E5 (asymmetric retrieval).
        """
        # E5 models require 'passage: ' prefix for document embeddings
        texts_for_embedding = [f"passage: {c['text']}" for c in chunks]
        embeddings = self.embedder.encode(texts_for_embedding, normalize_embeddings=True).tolist()
        
        self.collection.upsert(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],  # Documento originale (senza prefisso)
            metadatas=[c["metadata"] for c in chunks]
        )

    # ── Ricerca ibrida ──────────────────────────────────────────────

    def search(self, query: str, n_results: int = None) -> list[dict]:
        """
        Ricerca ibrida: combina ricerca semantica (embedding) con
        ricerca keyword (where_document $contains) usando Reciprocal Rank Fusion.
        Questo risolve il problema degli embedding model piccoli che non
        distinguono path API molto simili (es. prep-change-resident vs prep-change-registry).
        """
        n = n_results or config.max_retrieval_results

        # 1. Ricerca semantica
        semantic_results = self._semantic_search(query, n_results=n * 2)
        
        # 2. Ricerca keyword su termini specifici della query
        keyword_results = self._keyword_search(query, n_results=n * 2)
        
        # 3. Fusion con RRF (Reciprocal Rank Fusion)
        merged = self._rrf_merge(semantic_results, keyword_results, top_n=n)
        
        return merged
    
    def _semantic_search(self, query: str, n_results: int) -> list[dict]:
        """Ricerca puramente semantica con embedding E5."""
        query_for_embedding = f"query: {query}"
        query_embedding = self.embedder.encode(
            [query_for_embedding], normalize_embeddings=True
        ).tolist()
        
        # Filtra le descrizioni di immagini auto-generate (rumore)
        try:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                where={"chunk_type": {"$ne": "image_description"}},
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
        
        return self._parse_results(results)
    
    def _keyword_search(self, query: str, n_results: int) -> list[dict]:
        """
        Ricerca keyword: estrae termini tecnici specifici dalla query
        (path API, nomi SP, nomi tabelle) e cerca chunk che li contengono.
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []
        
        all_results = {}
        
        for kw in keywords:
            try:
                # ChromaDB where_document con $contains per match esatto
                where_filters = {
                    "$and": [
                        {"chunk_type": {"$ne": "image_description"}},
                    ]
                }
                results = self.collection.get(
                    where_document={"$contains": kw},
                    where={"chunk_type": {"$ne": "image_description"}},
                    include=["documents", "metadatas"],
                    limit=n_results
                )
            except Exception:
                try:
                    results = self.collection.get(
                        where_document={"$contains": kw},
                        include=["documents", "metadatas"],
                        limit=n_results
                    )
                except Exception:
                    continue
            
            if results and results["ids"]:
                for i, doc_id in enumerate(results["ids"]):
                    if doc_id not in all_results:
                        metadata = results["metadatas"][i]
                        if metadata.get("chunk_type") == "image_description":
                            continue
                        all_results[doc_id] = {
                            "id": doc_id,
                            "text": results["documents"][i],
                            "metadata": metadata,
                            "similarity": 0.9,  # Keyword match = alta rilevanza
                            "keyword_matches": 1
                        }
                    else:
                        # Più keyword matchano = più rilevante
                        all_results[doc_id]["keyword_matches"] += 1
        
        # Ordina per numero di keyword che matchano (più = meglio)
        ranked = sorted(
            all_results.values(), 
            key=lambda x: x.get("keyword_matches", 0), 
            reverse=True
        )
        
        return ranked[:n_results]
    
    def _extract_keywords(self, query: str) -> list[str]:
        """
        Estrae termini tecnici specifici dalla query per la ricerca keyword.
        Focus su: path API, nomi SP/package, nomi tabelle Oracle.
        """
        keywords = []
        
        # 1. Path API completi o parziali (es. /prep-change-resident)
        api_paths = re.findall(r'/[\w-]+(?:/[\w-]+)*', query)
        keywords.extend(api_paths)
        
        # 2. Segmenti di path con trattini (es. prep-change-resident)
        hyphenated = re.findall(r'\b[\w]+-[\w]+(?:-[\w]+)*\b', query)
        keywords.extend(hyphenated)
        
        # 3. Nomi Oracle-style (es. FOUE_EAI_PKG.Prepare_rdl_mre, P_STGOUT_...)
        oracle_names = re.findall(r'\b[A-Z_]{3,}(?:\.[A-Za-z_]+)?\b', query)
        keywords.extend(oracle_names)
        
        # 4. Nomi di package/procedure con punto (es. FOUE_EAI_PKG.Prepare_rdl_mre)
        dotted = re.findall(r'\b\w+\.\w+\b', query)
        keywords.extend(dotted)
        
        # Deduplicazione preservando ordine
        seen = set()
        unique = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen and len(kw) >= 4:
                seen.add(kw_lower)
                unique.append(kw)
        
        return unique
    
    def _rrf_merge(
        self, 
        semantic: list[dict], 
        keyword: list[dict], 
        top_n: int, 
        k: int = 60,
        keyword_weight: float = 1.5
    ) -> list[dict]:
        """
        Reciprocal Rank Fusion (RRF) per combinare risultati semantici e keyword.
        Formula: score = Σ 1/(k + rank_i)
        keyword_weight amplifica l'importanza dei match keyword esatti.
        """
        scores = {}  # id -> {score, result}
        
        # Score dai risultati semantici
        for rank, r in enumerate(semantic):
            rid = r["id"]
            rrf_score = 1.0 / (k + rank + 1)
            scores[rid] = {
                "score": rrf_score,
                "result": r
            }
        
        # Score dai risultati keyword (con peso maggiore)
        for rank, r in enumerate(keyword):
            rid = r["id"]
            rrf_score = keyword_weight / (k + rank + 1)
            if rid in scores:
                scores[rid]["score"] += rrf_score
            else:
                scores[rid] = {
                    "score": rrf_score,
                    "result": r
                }
        
        # Ordina per score RRF decrescente
        ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        
        # Ritorna i top_n con similarity normalizzata
        output = []
        for entry in ranked[:top_n]:
            result = entry["result"].copy()
            # Mantieni la similarity dal risultato semantico se disponibile,
            # altrimenti usa 0.9 per keyword match
            output.append(result)
        
        return output
    
    def _parse_results(self, results: dict) -> list[dict]:
        """Converte i risultati raw di ChromaDB in lista di dict."""
        output = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                distance = results["distances"][0][i]
                similarity = 1 - distance  # cosine distance → similarity
                
                metadata = results["metadatas"][0][i]
                
                if metadata.get("chunk_type") == "image_description":
                    continue
                
                if similarity >= config.similarity_threshold:
                    output.append({
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": metadata,
                        "similarity": round(similarity, 4)
                    })
        
        return output
    
    def count(self) -> int:
        return self.collection.count()
