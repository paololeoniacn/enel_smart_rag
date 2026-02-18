# Workflow Operativo (Quick Reference)

Questo documento spiega brevemente i passaggi chiave per gestire il progetto quando si passa da un contesto all'altro.

---

## 1. Setup Iniziale (Una Tantum)

Se è la prima volta che cloni il repo o sei su una macchina nuova:

```bash
# 1. Installa dipendenze (crea venv)
./handle_project.sh install

# 2. Scarica il modello Ollama (se non presente)
ollama pull qwen3:30b-a3b
```

---

## 2. Aggiornamento Knowledge Base

Ogni volta che hai nuovi documenti processati (es. in `processed_docs/`):

```bash
# 1. Pulisci la vecchia KB (opzionale, se vuoi ripartire da zero)
rm -rf chroma_store

# 2. Copia i nuovi file nella cartella monitored
cp processed_docs/*.md knowledge/docs/

# 3. Riesegui l'ingestione (Chunking + Embedding)
./handle_project.sh ingest
```

*Nota: L'ingestione è incrementale, ma se cambi la logica di chunking conviene pulire il DB (`chroma_store`) e rifarla.*

---

## 3. Avvio Applicazione

Per usare l'agente:

```bash
# Avvia interfaccia Web (Streamlit)
./handle_project.sh web
```

Oppure per la versione CLI (test rapidi):
```bash
./handle_project.sh start
```

---

## 4. Debug / Manutenzione

Se qualcosa non va (es. errori di import, venv corrotti):

```bash
# Pulisci file temporanei e cache
./handle_project.sh clean

# Reinstalla l'ambiente da zero
./handle_project.sh install
```
