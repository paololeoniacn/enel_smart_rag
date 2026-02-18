from pathlib import Path
import re

# === CHUNKER SPECIALIZZATO PER MARKDOWN PROCESSATI ===

def chunk_markdown_file(text: str, filename: str, chunk_size: int = 1500, overlap: int = 200) -> list[dict]:
    """
    Chunking ottimizzato per file Markdown pre-processati con Header di Metadati.
    """
    # 1. Estrazione Header e Metadati
    header_lines = []
    body_lines = []
    
    lines = text.split('\n')
    parsing_header = True
    
    metadata = {
        "source_file": filename,
        "original_path": "",
        "processing_date": ""
    }
    
    for i, line in enumerate(lines):
        if i < 20 and parsing_header: 
            line_strip = line.strip()
            if line_strip.startswith("**Percorso:**"):
                metadata["original_path"] = line_strip.replace("**Percorso:**", "").strip()
                header_lines.append(line)
                continue
            if line_strip.startswith("**File originale:**"):
                metadata["original_file"] = line_strip.replace("**File originale:**", "").strip()
                header_lines.append(line)
                continue
            if line_strip.startswith("**Data processing:**"):
                metadata["processing_date"] = line_strip.replace("**Data processing:**", "").strip()
                header_lines.append(line)
                continue
            
            if line_strip.startswith("# ") or line_strip.startswith("## ") or line_strip.startswith("|"):
                parsing_header = False
                body_lines.append(line)
            elif parsing_header:
                header_lines.append(line)
        else:
            body_lines.append(line)

    body_text = "\n".join(body_lines).strip()
    
    context_prefix = f"DOCUMENT CONTEXT:\nSource: {filename}\nPath: {metadata.get('original_path', 'N/A')}\n\nCONTENT:\n"

    # 2. Chunking del Body
    paragraphs = re.split(r'\n\s*\n', body_text)
    
    chunks = []
    current_chunk = ""
    chunk_index = 0
    
    for para in paragraphs:
        current_len = len(current_chunk) + len(context_prefix)
        para_len = len(para)
        
        if current_len + para_len > chunk_size:
            if current_chunk:
                chunks.append(_make_chunk(current_chunk, filename, chunk_index, metadata, context_prefix))
                chunk_index += 1
                current_chunk = ""
            
            if len(para) > chunk_size:
                 is_table = para.strip().startswith("|")
                 if is_table and len(para) < chunk_size * 2:
                     current_chunk = para 
                 else:
                     step = chunk_size - len(context_prefix)
                     for i in range(0, len(para), step):
                        sub_para = para[i:i+step]
                        chunks.append(_make_chunk(sub_para, filename, chunk_index, metadata, context_prefix))
                        chunk_index += 1
            else:
                current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
                
    if current_chunk:
        chunks.append(_make_chunk(current_chunk, filename, chunk_index, metadata, context_prefix))
        
    return chunks

# === CHUNKER STANDARD (FALLBACK PER ALTRI FORMATI) ===

def chunk_text(text: str, source: str, chunk_size: int = 1024, overlap: int = 128) -> list[dict]:
    """
    Chunking standard per file non processati (PDF, DOCX, TXT semplici).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    chunks = []
    current_chunk = ""
    chunk_index = 0
    
    for para in paragraphs:
        if len(para) > chunk_size:
            if current_chunk:
                chunks.append(_make_chunk(current_chunk, source, chunk_index, {"source": source}, ""))
                chunk_index += 1
                current_chunk = ""
            
            words = para.split()
            sub_chunk = ""
            for word in words:
                if len(sub_chunk) + len(word) + 1 > chunk_size:
                    chunks.append(_make_chunk(sub_chunk, source, chunk_index, {"source": source}, ""))
                    chunk_index += 1
                    overlap_words = sub_chunk.split()[-20:]
                    sub_chunk = " ".join(overlap_words) + " " + word
                else:
                    sub_chunk = sub_chunk + " " + word if sub_chunk else word
            if sub_chunk:
                current_chunk = sub_chunk
        
        elif len(current_chunk) + len(para) + 2 > chunk_size:
            chunks.append(_make_chunk(current_chunk, source, chunk_index, {"source": source}, ""))
            chunk_index += 1
            sentences = current_chunk.split(". ")
            overlap_text = ". ".join(sentences[-2:]) if len(sentences) > 2 else ""
            current_chunk = overlap_text + "\n\n" + para if overlap_text else para
        
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para
    
    if current_chunk:
        chunks.append(_make_chunk(current_chunk, source, chunk_index, {"source": source}, ""))
    
    return chunks


# === HELPER CONDIVISO ===

def _make_chunk(text: str, source: str, index: int, metadata: dict, context_prefix: str) -> dict:
    source_id = Path(source).stem.replace(" ", "_").lower().replace(".", "_")
    
    # Il testo vettorizzato include il prefisso di contesto
    full_text = context_prefix + text
    
    # Aggiorniamo i metadati
    chunk_metadata = metadata.copy()
    chunk_metadata.update({
        "chunk_index": index,
        "char_count": len(full_text),
        "source": source 
    })
    
    return {
        "id": f"{source_id}_chk_{index}",
        "text": full_text,
        "metadata": chunk_metadata
    }
