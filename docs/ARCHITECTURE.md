# sigfy RAG Layered Architecture

![sigfy RAG System Architecture](images/architecture.png)

## System Diagram

```
                 PRESENTATION LAYER (Thin Client)
     ┌────────────────────────────────────────────────────────┐
     │                      Gmail Add-on                      │
     │  • Contextual Card UI        • Editable Reply Draft    │
     │  • Provenance Citations      • Manual Insertion Action │
     └──────────────────────────┬─────────────────────────────┘
                                │ JSON Payload
                                ▼
                         API / TRACE LAYER
     ┌────────────────────────────────────────────────────────┐
     │                   FastAPI (main.py)                    │
     │  • /draft & /health          • API shared secret auth  │
     │  • Latency profiling metrics • Privacy-aware request ID│
     └──────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                        RETRIEVAL LAYER
     ┌────────────────────────────────────────────────────────┐
     │                  Retriever (retrieval.py)              │
     │  • Metadata-guided filtering with automatic fallback   │
     │  • Stopword-filtered BM25    • Dense semantic search   │
     │  • Reciprocal Rank Fusion (RRF) ranking                │
     └──────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                    EVIDENCE VALIDATION GATE
     ┌────────────────────────────────────────────────────────┐
     │               validate_evidence helper                 │
     │  • Multi-signal dense & lexical scoring validation     │
     │  • Pass: Proceed to Response Generation                │
     │  • Reject: Bypasses LLM, immediately returns Not Found │
     └────────────────────────┬───────────────────────────────┘
                              │ Valid Evidence
                              ▼
                       GENERATION LAYER
     ┌────────────────────────────────────────────────────────┐
     │                 Generator (generate.py)                │
     │  • Grounded Response Generation (Groq LLM)             │
     │  • Provenance citation compiler                        │
     └────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                        KNOWLEDGE LAYER
     ┌────────────────────────────────────────────────────────┐
     │                Pre-computed Plan Index                 │
     │  • Offline chunks.json       • Cached embeddings.npy   │
     │  • Chunks generated offline; query embedded online     │
     └────────────────────────────────────────────────────────┘
```

---

## Detailed RAG Execution Flow

### 1. Ingestion vs. Query-Time Embeddings
To keep query latency low (`< 15ms` for retrieval), expensive vector embedding generation is split:
- **Offline Ingestion (`ingest.py`)**: PDFs are parsed, windowed into ~1,100-character chunks on sentence boundaries, embedded locally in batches using `SentenceTransformer (BAAI/bge-small-en-v1.5)`, and saved to `embeddings.npy`.
- **Online Query-Time**: Only the single incoming query is embedded dynamically. Vector similarity is run as a direct numpy matrix dot product (flat index) on CPU.

### 2. Lexical RRF Bias
Hybrid RRF assigns a higher weight to BM25 (`1.5`) than Dense similarity (`1.0`). Exact term matches (such as a specific limit like `"$3,300"`, copays, and carrier names) are far more reliable in insurance contexts than semantic embeddings, which can suffer from noise.

### 3. Stopword Filtering
Before lexical indexing and query search, common prepositions and conjunctions (e.g. *what*, *is*, *the*, *of*, *it*) are filtered. This prevents nonsense queries or general conversational text from artificially inflating BM25 scores.

### 4. Multi-Signal Evidence Validation Gate
Bypassing the LLM on insufficient evidence saves API costs and guarantees zero hallucination. Rather than a simple `OR` gate, the Validation Gate checks a nuanced combination of signals:
- **Accept** if:
  - `(dense_score >= settings.val_dense_threshold AND bm25_score >= settings.val_bm25_minimal)` (both vectors and keywords agree)
  - OR `bm25_score >= settings.val_bm25_strong` (strong keyword match)
  - OR `dense_score >= settings.val_dense_very_high` (strong semantic match)
- **Reject** otherwise, bypassing the LLM.
- *Note*: Thresholds are configurable via environment variables and tuned empirically. In production, they would be calibrated using offline evaluation against a labeled query validation set.

### 5. Metadata-Guided Retrieval with Fallback
When a query is received, **sigfy** scans the text for keywords corresponding to specific plans in `PLAN_DOCS` (e.g., "braces" matching the Dental plan).
- **Execution**: The search preferentially searches the detected document set and automatically falls back to the full corpus when evidence is weak. This prevents accidental misses when plan names are omitted while drastically reducing noise for clear queries.

### 6. Provenance-Rich Citations
Citations are compiled with complete self-contained metadata that separates user-facing presentation from internal debugging tools:
- **Visible fields**: `document`, `section`, `page`, `quote`.
- **Internal debugging fields**: `chunk_id`, `retrieval_score`, `effective_date`.

### 7. Privacy-Aware Tracing & Latency Metrics
To comply with standard PII (personally identifiable information) guidelines, the FastAPI console logs **never** write the raw query text or private email bodies. Instead, it logs a request ID hash, retrieved chunk IDs, scores, gate decisions, LLM status, and latency profiling metrics (time in milliseconds for embedding, dense, BM25, and LLM).
