### Sezione "Analisi del System Prompt: V1 vs V2"
Per tracciare l'evoluzione della "personalità" dell'Agente.

---

## 📅 VERSIONE 1.0 (Attuale) - "L'Assistente Generico"

Questo prompt è quello usato finora (Step 1-561). È un prompt "all-purpose" per un assistente RAG, focalizzato su ricerca generica e sintesi.

```python
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
6. Se non trovi risposta, DILLO chiaramente — non inventare...
(segue elenco strumenti generici)
"""
```

### ❌ Punti Deboli Rilevati (con Qwen 14B):
1.  **Troppa libertà**: Permette all'agente di "dedurre" o usare frasi come "sembra essere correlato a...". Nel dominio tecnico (API -> SP -> Tabella), questo è pericoloso.
2.  **Verboso**: Tende a scrivere paragrafi introduttivi ("Mi spiace ma...", "Ora cercherò...").
3.  **Poco tecnico**: Non ha direttive specifiche su cosa cercare (nomi di procedure, tabelle, parametri).

---

## 🎯 VERSIONE 2.0 (Proposed) - "Il Reverse Engineer Preciso"

Questo nuovo prompt trasforma l'agente in un analista tecnico specializzato.

### Cambiamenti Chiave:
1.  **Ruolo Definito**: "Senior Data Engineer specializzato in Reverse Engineering di sistemi Legacy/Microservizi".
2.  **Focus su Entità**: Istruzioni esplicite per cercare `API Endpoints`, `Stored Procedures` (Oracle/PLSQL), `Tabelle`, `Campi`.
3.  **Anti-Allucinazione Rigida**: "Se il documento non menziona esplicitamente la relazione, scrivi `[NON SPECIFICATO]`. Non inferire basandoti solo sul nome."
4.  **Formato Output**: Richiede risposte strutturate (Elenco puntato, JSON o Tabelle Markdown) per facilitare la lettura rapida.
5.  **Stop Condition**: "Se dopo 2 ricerche non trovi l'esatto match, fermati e riporta i parziali. Non andare in loop."

### Obiettivo:
Ottenere con il **14B** la stessa precisione "chirurgica" che il **30B** aveva naturalmente grazie alla sua maggiore capacità di comprensione, ma forzandola tramite regole esplicite.
