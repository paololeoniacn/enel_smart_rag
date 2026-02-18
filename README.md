# Sistema Agentico Locale

Questo progetto implementa un sistema agentico RAG locale basato su Qwen3-30B-A3B (via Ollama), ChromaDB e Python.

## Setup

1.  **Prerequisiti**
    Assicurati di avere installato Ollama:
    ```bash
    brew install ollama
    ```

2.  **Modello**
    Avvia Ollama e scarica il modello raccomandato:
    ```bash
    ollama serve
    # In un nuovo terminale:
    ollama pull qwen3:30b-a3b
    ```

3.  **Ambiente Python**
    Consigliato creare un ambiente virtuale:
    ```bash
    cd agentic-system
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

4.  **Ingestione Documenti**
    Metti i tuoi documenti (PDF, Markdown, TXT, DOCX) nella cartella `knowledge/docs`.
    Poi esegui lo script di ingestione:
    ```bash
    python -m ingest.ingest
    ```
    *(Nota: Esegui come modulo dalla root del progetto per risolvere correttamente gli import)*

5.  **Avvio**
    Avvia l'orchestratore:
    ```bash
    python main.py
    ```

## Struttura
- `orchestrator.py`: Logica principale e gestione tool call.
- `tools/knowledge_base.py`: Interfaccia con ChromaDB.
- `ingest/`: Script per processare documenti.
- `config.py`: Configurazione centralizzata.
