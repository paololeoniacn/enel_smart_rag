import time
import ollama
from config import config
from tools.knowledge_base import KnowledgeBase


class Orchestrator:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.conversation_history = []

    # ── Helper: chiamata LLM semplice ──────────────────────────────
    def _call_llm(self, messages: list[dict], max_tokens: int | None = None) -> str:
        """Chiamata LLM pura, senza tool. Ritorna solo il testo."""
        response = ollama.chat(
            model=config.model_name,
            messages=messages,
            options={
                "temperature": config.temperature,
                "num_ctx": config.num_ctx,
                "num_predict": max_tokens or config.max_tokens,
            }
        )
        return response["message"]["content"].strip()

    # ── Step 1: Query Rewriting ────────────────────────────────────
    def _rewrite_query(self, user_input: str, attempt: int = 0) -> str:
        """
        Riformula la domanda dell'utente in una query di ricerca ottimizzata.
        Al tentativo > 0, chiede esplicitamente di variare la formulazione.
        """
        if attempt == 0:
            prompt = user_input
        else:
            prompt = (
                f"{user_input}\n\n"
                f"(La ricerca precedente non ha trovato risultati sufficienti. "
                f"Tentativo {attempt + 1}: riformula usando termini tecnici diversi, "
                f"nomi di tabelle, stored procedure, o path API esatti.)"
            )

        rewritten = self._call_llm(
            messages=[
                {"role": "system", "content":
                 "Sei un esperto di ricerca documentale tecnica. "
                 "Riformula la domanda dell'utente in una query di ricerca "
                 "efficace per trovare informazioni in documentazione tecnica "
                 "di microservizi (API, stored procedure, tabelle Oracle). "
                 "Rispondi SOLO con la query riformulata, nient'altro. "
                 "Usa termini tecnici specifici."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )
        return rewritten

    # ── Step 2: Dual KB Search (original + rewritten) ─────────
    def _search_and_format(self, original_query: str, rewritten_query: str, n_results: int = None) -> tuple[str, int]:
        """
        Doppia ricerca: query originale + riscritta, 
        con deduplicazione per chunk ID e ordinamento per similarità.
        """
        n = n_results or config.max_retrieval_results
        
        # Ricerca con entrambe le query
        results_orig = self.kb.search(query=original_query, n_results=n)
        results_rewr = self.kb.search(query=rewritten_query, n_results=n)
        
        # Dedup per ID, tenendo la similarità più alta
        seen = {}
        for r in results_orig + results_rewr:
            rid = r["id"]
            if rid not in seen or r["similarity"] > seen[rid]["similarity"]:
                seen[rid] = r
        
        # Ordina per similarità decrescente
        merged = sorted(seen.values(), key=lambda x: x["similarity"], reverse=True)[:n]

        if not merged:
            return "Nessun risultato trovato nella knowledge base.", 0

        output = []
        for r in merged:
            source = r["metadata"].get("source", "sconosciuta")
            section = r["metadata"].get("section", "")
            section_str = f" § {section}" if section else ""
            sim = r["similarity"]
            output.append(
                f"[Fonte: {source}{section_str}] (sim: {sim:.3f})\n{r['text']}"
            )

        return "\n\n---\n\n".join(output), len(merged)

    # ── Step 3: Context Sufficiency Check ──────────────────────────
    def _is_context_sufficient(self, context: str, user_input: str) -> bool:
        """
        Verifica se il contesto recuperato contiene informazioni
        sufficienti per rispondere alla domanda.
        """
        response = self._call_llm(
            messages=[
                {"role": "system", "content":
                 "Rispondi SOLO con SI o NO. Nient'altro."},
                {"role": "user", "content":
                 f"Il seguente contesto contiene informazioni sufficienti "
                 f"per rispondere a questa domanda?\n\n"
                 f"Domanda: {user_input}\n\n"
                 f"Contesto (estratto):\n{context[:4000]}"}
            ],
            max_tokens=10
        )
        return "SI" in response.upper()

    # ── Step 4: Final Answer Generation ────────────────────────────
    def _generate_answer(self, context: str, user_input: str) -> str:
        """Genera la risposta finale basandosi sul contesto recuperato."""
        return self._call_llm(
            messages=[
                {"role": "system", "content":
                 "Sei un assistente tecnico preciso e conciso. "
                 "Rispondi in ITALIANO, in modo diretto. "
                 "Usa SOLO le informazioni presenti nel contesto fornito. "
                 "Non inventare informazioni. "
                 "Se il contesto non contiene la risposta, dillo esplicitamente."},
                {"role": "user", "content":
                 f"Contesto:\n{context}\n\n"
                 f"Domanda: {user_input}"}
            ]
        )

    # ── Pipeline Principale ────────────────────────────────────────
    def query(self, user_input: str, callback=None) -> str:
        """
        Pipeline RAG Ibrida:
        1. Query Rewriting (LLM)
        2. KB Search (automatico)
        3. Context Check (LLM)
        4. Answer Generation (LLM)
        """

        print("\n\n" + "=" * 60)
        print(f"🏁 STARTING QUERY: {user_input}")
        print("=" * 60 + "\n")

        max_attempts = 3
        context = ""
        sufficient = False

        for attempt in range(max_attempts):
            # ── Step 1: Query Rewriting ──
            t0 = time.perf_counter()
            rewritten = self._rewrite_query(user_input, attempt=attempt)
            t1 = time.perf_counter()

            print(f"--- [ATTEMPT {attempt + 1}/{max_attempts}] ---")
            print(f"📝 REWRITTEN QUERY ({t1 - t0:.2f}s): {rewritten}")
            if callback:
                callback(f"🔍 Ricerca: **{rewritten[:80]}**")

            # ── Step 2: Dual KB Search ──
            t0 = time.perf_counter()
            context, n_results = self._search_and_format(user_input, rewritten)
            t1 = time.perf_counter()

            print(f"📄 KB SEARCH ({t1 - t0:.2f}s): {n_results} risultati")
            if callback:
                callback(f"📄 Trovati {n_results} risultati")

            if n_results == 0:
                print("⚠️ Nessun risultato. Riprovo con query diversa.")
                if callback:
                    callback("⚠️ Nessun risultato, riformulo...")
                continue

            # ── Step 3: Context Check ──
            t0 = time.perf_counter()
            sufficient = self._is_context_sufficient(context, user_input)
            t1 = time.perf_counter()

            print(f"🧪 CONTEXT CHECK ({t1 - t0:.2f}s): {'✅ SUFFICIENTE' if sufficient else '❌ INSUFFICIENTE'}")

            if sufficient:
                if callback:
                    callback("✅ Contesto sufficiente, genero risposta...")
                break
            else:
                print("🔄 Contesto insufficiente, riformulo...")
                if callback:
                    callback("🔄 Contesto insufficiente, riformulo...")

        # ── Step 4: Final Answer ──
        print("\n--- [FINAL ANSWER GENERATION] ---")
        t0 = time.perf_counter()
        answer = self._generate_answer(context, user_input)
        t1 = time.perf_counter()

        print(f"🤖 ANSWER ({t1 - t0:.2f}s):\n{answer}\n")

        # Aggiorna conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": answer})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-16:]

        return answer
