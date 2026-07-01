from pathlib import Path
from tools.knowledge_base import KnowledgeBase
from ingest.chunker import chunk_markdown_file, chunk_text

# Per PDF: pip install pymupdf --break-system-packages
# Per DOCX: pip install python-docx --break-system-packages

def extract_text(file_path: Path) -> str:
    """Estrae testo da diversi formati."""
    suffix = file_path.suffix.lower()
    
    if suffix == ".txt" or suffix == ".md":
        return file_path.read_text(encoding="utf-8")
    
    elif suffix == ".pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(str(file_path))
        text = ""
        for page_num, page in enumerate(doc):
            text += f"\n\n[Pagina {page_num + 1}]\n{page.get_text()}"
        doc.close()
        return text
    
    elif suffix == ".docx":
        from docx import Document
        doc = Document(str(file_path))
        return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    
    else:
        raise ValueError(f"Formato non supportato: {suffix}")


def ingest_directory(directory: str = "./knowledge/docs"):
    """Ingerisce tutti i documenti da una cartella."""
    kb = KnowledgeBase()
    dir_path = Path(directory)
    
    supported = {".txt", ".md", ".pdf", ".docx"}
    # Ensure directory exists
    if not dir_path.exists():
        print(f"Directory {dir_path} does not exist. Creating it.")
        dir_path.mkdir(parents=True, exist_ok=True)
        
    files = [f for f in dir_path.rglob("*") if f.suffix.lower() in supported]
    
    if not files:
        print(f"Nessun file trovato in {dir_path}")
        return

    # Reset della collection per re-indicizzazione pulita
    print(f"🔄 Reset knowledge base...")
    kb.reset()

    total_chunks = 0
    all_chunks = []  # Per il report finale
    
    for file_path in files:
        print(f"📄 Processando: {file_path.name}")
        try:
            text = extract_text(file_path)
            if file_path.suffix.lower() == ".md":
                chunks = chunk_markdown_file(text, filename=file_path.name)
            else:
                chunks = chunk_text(text, source=file_path.name)
                
            kb.add_documents(chunks)
            total_chunks += len(chunks)
            all_chunks.extend(chunks)
            print(f"   ✓ {len(chunks)} chunk creati")
        except Exception as e:
            print(f"   ✗ Errore: {e}")
    
    print(f"\n✅ Ingestione completata: {len(files)} file → {total_chunks} chunk")
    print(f"   Totale documenti in knowledge base: {kb.count()}")
    
    # Report sezioni per documento
    print(f"\n{'='*70}")
    print(f"📊 REPORT CONTEXTUAL SECTIONS")
    print(f"{'='*70}")
    
    from collections import defaultdict
    doc_sections = defaultdict(lambda: defaultdict(int))
    
    for c in all_chunks:
        source = c["metadata"].get("source", "?")
        section = c["metadata"].get("section", "—")
        doc_sections[source][section] += 1
    
    for source in sorted(doc_sections.keys()):
        sections = doc_sections[source]
        total = sum(sections.values())
        print(f"\n📄 {source} ({total} chunks)")
        for section, count in sections.items():
            print(f"   {'├' if section != list(sections.keys())[-1] else '└'}── [{count:2d}] {section}")


if __name__ == "__main__":
    ingest_directory()
