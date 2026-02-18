import json
import re
import time
import ollama
from config import config
from tools.knowledge_base import KnowledgeBase

SYSTEM_PROMPT = """
Sei un sistema agentico di ricerca e analisi documentale. Il tuo compito è rispondere
alle domande dell'utente con la massima accuratezza, utilizzando strumenti specifici
per cercare, verificare e sintetizzare informazioni.

## PRINCIPI FONDAMENTALI

1. MAI rispondere basandoti solo sulla tua conoscenza interna quando hai strumenti disponibili
2. SEMPRE cercare nelle fonti prima di rispondere
3. Se la prima ricerca non è sufficiente, RIFORMULA e cerca di nuovo (max 3 tentativi)
4. Se trovi informazioni contraddittorie, SEGNALALO esplicitamente
5. CITA sempre la fonte specifica (nome documento, sezione, pagina se disponibile)
6. Se non trovi risposta, DILLO chiaramente — non inventare

## STRUMENTI DISPONIBILI

### search_knowledge_base
Cerca nella knowledge base locale.
Parametri: {"query": "stringa di ricerca", "n_results": 5}
Usa questo strumento come PRIMA azione per qualsiasi domanda fattuale.


### verify_claim
Verifica un'affermazione cercando conferme o smentite nelle fonti.
Parametri: {"claim": "affermazione da verificare", "context": "contesto originale"}
Usa DOPO aver ottenuto risultati dal retriever, per validare informazioni critiche.

### ask_user_clarification
Chiedi chiarimenti all'utente se la domanda è ambigua.
Parametri: {"question": "domanda di chiarimento"}
Usa SOLO se la domanda è genuinamente ambigua, non per pigrizia.

## WORKFLOW DECISIONALE

Per ogni query, segui questo processo:

STEP 1 — ANALISI
- La domanda è chiara o ambigua?
- Che tipo di informazione serve? (fattuale, numerica, procedurale, comparativa)
- Servono dati da più fonti?

STEP 2 — RICERCA
- Esegui search_knowledge_base con la query più specifica possibile
- Valuta i risultati: sono pertinenti? Rispondono alla domanda?
- Se insufficienti: riformula con sinonimi, termini più ampi/specifici
- Se serve: integra con search_structured_data

STEP 3 — VALIDAZIONE (se il contesto lo richiede)
- Per informazioni critiche (numeri, date, policy): usa verify_claim
- Per informazioni da più fonti: confronta e segnala discrepanze

STEP 4 — SINTESI
- Componi la risposta in modo chiaro e strutturato
- Includi citazioni esplicite: [Fonte: nome_documento, sezione X]
- Se ci sono incertezze, dichiarale
- Se la risposta è parziale, segnala cosa manca

## FORMATO DELLE TOOL CALL

Quando vuoi usare uno strumento, rispondi ESATTAMENTE in questo formato:

<tool_call>
{"name": "nome_strumento", "arguments": {"param1": "valore1"}}
</tool_call>

Attendi il risultato prima di proseguire. Puoi fare più tool call in sequenza.

## COMPORTAMENTO IN CASO DI ERRORE

- Se uno strumento fallisce: riprova con parametri diversi (1 volta)
- Se fallisce di nuovo: segnala il problema e rispondi con quello che hai
- MAI fingere di aver trovato qualcosa che non hai trovato
"""

class Orchestrator:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.conversation_history = []
    
    def _call_llm(self, messages: list[dict]) -> str:
        response = ollama.chat(
            model=config.model_name,
            messages=messages,
            options={
                "temperature": config.temperature,
                "num_ctx": config.num_ctx,
                "num_predict": config.max_tokens,
            }
        )
        return response["message"]["content"]
    
    def _parse_tool_calls(self, response: str) -> list[dict]:
        """Estrae tool call dal response del modello."""
        pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
        matches = re.findall(pattern, response, re.DOTALL)
        
        calls = []
        for match in matches:
            try:
                calls.append(json.loads(match))
            except json.JSONDecodeError:
                continue
        return calls
    
    def _parse_tool_calls_robust(self, response: str) -> list[dict]:
        """Estrae tool call cercando sia tag XML che blocchi JSON liberi."""
        # 1. Prova con i tag XML (metodo standard)
        pattern_xml = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
        matches = re.findall(pattern_xml, response, re.DOTALL)
        if matches:
            calls = []
            for match in matches:
                try:
                    calls.append(json.loads(match))
                except json.JSONDecodeError:
                    continue
            return calls
            
        # 2. Fallback: Prova a cercare un JSON object isolato
        # Cerca { "name": "...", "arguments": { ... } }
        try:
            # Pulisce markdown code blocks se presenti (```json ... ```)
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text.rsplit("\n", 1)[0]
            
            # Cerca il primo '{' e l'ultimo '}'
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                json_str = text[start:end+1]
                data = json.loads(json_str)
                # Verifica struttura minima
                if isinstance(data, dict) and "name" in data and "arguments" in data:
                    return [data]
        except Exception:
            pass
            
        return []
    
    def _execute_tool(self, tool_call: dict) -> str:
        """Esegue uno strumento e restituisce il risultato."""
        name = tool_call.get("name")
        args = tool_call.get("arguments", {})
        
        if name == "search_knowledge_base":
            results = self.kb.search(
                query=args.get("query", ""),
                n_results=args.get("n_results", config.max_retrieval_results)
            )
            if not results:
                return "Nessun risultato trovato nella knowledge base per questa query."
            
            output = []
            for r in results:
                source = r["metadata"].get("source", "sconosciuta")
                page = r["metadata"].get("page", "")
                page_str = f", pagina {page}" if page else ""
                output.append(
                    f"[Fonte: {source}{page_str}] (similarità: {r['similarity']})\n{r['text']}"
                )
            return "\n\n---\n\n".join(output)
        
        elif name == "verify_claim":
            claim = args.get("claim", "")
            # Cerca conferme/smentite della claim
            results = self.kb.search(query=claim, n_results=5)
            if not results:
                return f"Impossibile verificare: '{claim}' — nessuna fonte trovata."
            
            sources_text = "\n".join([
                f"- [{r['metadata'].get('source', '?')}] {r['text'][:200]}..."
                for r in results
            ])
            return f"Fonti trovate per la verifica di '{claim}':\n{sources_text}"
        
        elif name == "ask_user_clarification":
            # Questo viene gestito a livello di interfaccia
            return f"CLARIFICATION_NEEDED: {args.get('question', '')}"
        
        else:
            return f"Strumento '{name}' non riconosciuto."
    
    
    def query(self, user_input: str, callback=None) -> str:
        """
        Processo principale: query → tool calls → risposta.
        callback(msg): funzione opzionale per riportare progresso all'UI.
        """
        
        
        print("\n\n" + "="*50)
        print(f"🏁 STARTING QUERY: {user_input}")
        print("="*50 + "\n")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.conversation_history,
            {"role": "user", "content": user_input}
        ]
        
        max_iterations = 6  # Previene loop infiniti
        full_response = ""
        
        for iteration in range(max_iterations):
            print(f"\n--- [ITERATION {iteration + 1}] ---")
            
            start_time = time.perf_counter()
            response = self._call_llm(messages)
            elapsed = time.perf_counter() - start_time
            
            print(f"🤖 AGENT RESPONSE ({elapsed:.2f}s):\n{response}\n")

            # Estrai il "pensiero" (testo prima del tool call)
            thought = response.split("<tool_call>")[0].strip()
            if thought:
                print(f"💭 THOUGHT:\n{thought}")
                if callback:
                    callback(f"🤔 {thought[:200]}...")
            
            tool_calls = self._parse_tool_calls_robust(response)
            
            if not tool_calls:
                print("🏁 No tool calls found. Final response.")
                full_response = response
                break
            
            # Esegui ogni tool call
            print(f"🛠️ FOUND {len(tool_calls)} TOOL CALLS: {tool_calls}")
            tool_results = []
            
            for tc in tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_args = tc.get("arguments", {})
                
                print(f"👉 EXECUTING {tool_name} with args: {tool_args}")
                if callback:
                    callback(f"🛠️ Eseguo tool: **{tool_name}** ({str(tool_args)[:100]}...)")
                
                t_start = time.perf_counter()
                result = self._execute_tool(tc)
                t_elapsed = time.perf_counter() - t_start
                
                print(f"✅ TOOL COMPLETED in {t_elapsed:.2f}s")
                print(f"📄 RESULT PREVIEW: {result[:200]}...")
                
                if callback:
                    match_count = result.lower().count("[fonte:")
                    preview = result[:100].replace("\n", " ") + "..."
                    if match_count > 0:
                        callback(f"📄 Trovati {match_count} risultati. ({preview})")
                    else:
                        callback(f"⚠️ Risultato: {preview}")
                
                # Gestisci richiesta di chiarimento
                if result.startswith("CLARIFICATION_NEEDED:"):
                    question = result.replace("CLARIFICATION_NEEDED: ", "")
                    # Potremmo dover gestire meglio questo in un loop reale, 
                    # qui ritorniamo la domanda all'utente
                    return f"🔍 Ho bisogno di un chiarimento: {question}"
                
                tool_results.append({
                    "tool": tc["name"],
                    "query": tc["arguments"],
                    "result": result
                })
            
            # Aggiungi risultati al contesto
            tool_output = "\n\n".join([
                f"## Risultato di {tr['tool']}:\n{tr['result']}"
                for tr in tool_results
            ])
            
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Ecco i risultati degli strumenti:\n\n{tool_output}\n\nOra prosegui con il tuo workflow."})
        
        # Salva nella storia conversazionale
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": full_response})
        
        # Tieni la storia gestibile
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-16:]
        
        return full_response
