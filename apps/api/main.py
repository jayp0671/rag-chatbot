import os, json, uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ingest import extract_text_from_pdf, clean_text, chunk_text
from retriever import VectorStore, Embedder, HFAPIEmbedder
from llm import LLMClient

# -------- Paths & config --------
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
for p in [DATA_DIR, DATA_DIR / "uploads", DATA_DIR / "index", DATA_DIR / "meta"]:
    p.mkdir(parents=True, exist_ok=True)

INDEX_DIR = Path(os.getenv("INDEX_DIR", str(DATA_DIR / "index"))).resolve()
META_DIR = DATA_DIR / "meta"
UPLOADS_DIR = DATA_DIR / "uploads"

MODEL_EMBED = os.getenv("MODEL_EMBED", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "local")  # "local" or "hf_api"

# -------- App --------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# -------- Embedding + store + LLM --------
if EMBED_PROVIDER == "hf_api":
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    if not HF_TOKEN:
        raise RuntimeError("EMBED_PROVIDER=hf_api but HF_TOKEN is not set")
    embedder = HFAPIEmbedder(MODEL_EMBED, HF_TOKEN)
else:
    embedder = Embedder(MODEL_EMBED)

store = VectorStore(index_dir=INDEX_DIR)
llm = LLMClient()

# -------- Models --------
class SearchReq(BaseModel):
    q: str
    top_k: int = 5

class AskReq(BaseModel):
    question: str
    top_k: int = 5

class AskResp(BaseModel):
    answer: str
    citations: List[dict]

# -------- Helpers --------
def _load_meta(doc_id: str):
    p = META_DIR / f"{doc_id}.json"
    if not p.exists():
        raise HTTPException(404, "document_id not found")
    return json.loads(p.read_text("utf-8"))

def _save_meta(doc_id: str, title: str):
    meta = {"document_id": doc_id, "title": title}
    (META_DIR / f"{doc_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return meta

# -------- Endpoints --------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    name = file.filename or "uploaded"
    lower = name.lower()
    if not (lower.endswith(".pdf") or lower.endswith(".txt")):
        raise HTTPException(400, "Only PDF or TXT allowed")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "File > 25MB rejected")
    doc_id = str(uuid.uuid4())
    ext = ".pdf" if lower.endswith(".pdf") else ".txt"
    out_path = UPLOADS_DIR / f"{doc_id}{ext}"
    out_path.write_bytes(content)
    _save_meta(doc_id, name)
    return {"document_id": doc_id, "title": name}

@app.post("/ingest")
def ingest(document_id: str = Query(..., alias="document_id")):
    _ = _load_meta(document_id)
    pdf_path = UPLOADS_DIR / f"{document_id}.pdf"
    txt_path = UPLOADS_DIR / f"{document_id}.txt"

    if pdf_path.exists():
        raw = extract_text_from_pdf(str(pdf_path))
    elif txt_path.exists():
        raw = txt_path.read_text("utf-8", errors="ignore")
    else:
        raise HTTPException(404, "Uploaded file not found")

    cleaned = clean_text(raw)
    chunks = chunk_text(cleaned)

    # Safety cap so your laptop doesn't freeze; raise later as needed
    MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "5"))
    chunks = chunks[:MAX_CHUNKS]

    if not chunks:
        raise HTTPException(400, "No extractable text")

    # small batches to be gentle on the machine / free APIs
    BATCH = 8
    vectors = []
    for i in range(0, len(chunks), BATCH):
        vectors.extend(embedder.encode(chunks[i : i + BATCH]))

    items = [
        {"chunk_id": f"{document_id}:{i}", "document_id": document_id, "text": ch}
        for i, ch in enumerate(chunks)
    ]

    store.add(items, vectors)
    return {"status": "ready", "document_id": document_id, "chunks": len(items)}

@app.post("/search")
def search(req: SearchReq):
    if not store.ready():
        raise HTTPException(400, "Index not found. Ingest a document first.")
    q_vec = embedder.encode([req.q])[0]
    hits = store.search(q_vec, top_k=req.top_k)
    out = [
        {
            "chunk_id": h["chunk_id"],
            "document_id": h["document_id"],
            "text": h["text"][:800],
            "score": h["score"],
        }
        for h in hits
    ]
    return {"results": out}

@app.post("/ask", response_model=AskResp)
def ask(req: AskReq):
    if not store.ready():
        raise HTTPException(400, "Index not found. Ingest a document first.")
    q_vec = embedder.encode([req.question])[0]
    hits = store.search(q_vec, top_k=req.top_k)
    if not hits:
        return AskResp(answer="I do not know based on the documents provided.", citations=[])
    ctx_lines = [f"- [{h['chunk_id']}] doc={h['document_id']} :: {h['text'][:800]}" for h in hits]
    system = "You are precise. Only answer from the provided context. If the context is missing, say you do not know."
    user = f"Question: {req.question}\n\nContext:\n" + "\n".join(ctx_lines)
    answer = llm.generate(system=system, user=user)
    citations = [
        {
            "document_id": h["document_id"],
            "chunk_id": h["chunk_id"],
            "snippet": h["text"][:160],
            "score": h["score"],
        }
        for h in hits[: max(2, min(5, req.top_k))]
    ]
    return AskResp(answer=answer, citations=citations)
