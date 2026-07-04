# sigfy: RAG-Powered Benefits Email Assistant

**sigfy** is a Gmail Workspace Add-on backed by a FastAPI Retrieval-Augmented Generation (RAG) service. It helps benefits account managers draft accurate, evidence-backed replies using the provided benefits documents.

This project was built as a take-home assignment to demonstrate grounded document retrieval, citation-based response generation, and a Gmail Workspace Add-on experience.

The implementation focuses on the core assignment requirements:
* **Real Gmail Add-on UI**: A contextual sidebar rendering editable drafts and citations directly in Gmail.
* **Grounded Retrieval**: Restricts the prompt context to document-grounded search evidence rather than stuffing full documents.
* **Visible Citations**: Every claim is mapped to the exact document, section, and page.
* **Grounded Response Generation**: The LLM generates replies using only the retrieved evidence and explicitly cites the supporting documents.
* **Explicit "Not Found" Handling**: Bypasses the LLM completely when plan documents do not contain a clear answer.

> **Assumption:** The provided benefits documents are treated as the authoritative source of truth. If sufficient supporting evidence cannot be retrieved, the assistant returns a "not found" response instead of generating an unsupported answer.

---

## 1. How Retrieval & Answer Logic Works

Instead of sending the entire document corpus to the LLM, the system first retrieves only the most relevant sections before generating a response:
1. **Ingestion (Offline)**: Every PDF document is parsed, cleaned, and split into ~1,100-character chunks tagged with metadata (`document`, `page`, `section heading`, and `effective_date`).
2. **Metadata-Guided Retrieval**: When an email is opened, the query is scanned for keywords matching specific documents. Retrieval preferentially searches this plan subset to reduce search noise. If matches are weak, it falls back to the full corpus.
3. **Hybrid Search & Fusion**: Chunks are scored via stopword-filtered lexical search (BM25) and dense semantic embeddings (`bge-small-en-v1.5`), then combined using Reciprocal Rank Fusion (RRF).
4. **Evidence Validation Gate**: Before invoking the LLM, the top matches are validated against similarity thresholds. If scores are too low, the LLM is bypassed, and a "not found" fallback draft is returned.
5. **Grounded Response Generation**: The LLM synthesizes a response using the retrieved evidence only, selecting the most recent applicable policy when multiple document versions are retrieved.

*For a detailed technical layout, see the [Layered Architecture Deep-Dive](docs/ARCHITECTURE.md).*

---

## 2. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Hybrid BM25 + Dense** | Combines exact terminology (figures, deductibles, carrier names) with semantic matching (synonyms like *braces* → *orthodontic*). |
| **Metadata-Guided Retrieval** | Preferentially searches matched plan documents to reduce noise while maintaining full-corpus fallback. |
| **Evidence Validation Gate** | Blocks LLM calls on out-of-scope or nonsense queries to prevent hallucinations and save tokens. |
| **Offline Embedding Caching** | Embeddings are computed once offline; only the query is embedded online (`< 15ms` latency). |
| **Separated Citation Fields** | Separates user-facing fields (`document`, `page`, `section`) from internal developer provenance (`chunk_id`, `score`). |

---

## 3. What Was Most Challenging

The biggest challenge was **balancing retrieval precision with recall** across multiple benefits documents containing overlapping vocabularies. For instance, a query about *orthodontics* can retrieve semantically similar but outdated tables from earlier plan years, leading a naive RAG model to quote a stale limit. 

To overcome this, I developed **Metadata-Guided Retrieval** to isolate plan scopes, slightly increased the BM25 weighting (`1.5` vs. `1.0`) to lock onto exact numbers, and built temporal parsing that forces the LLM to compare effective dates and note superseded policy versions.

---

## 4. Accuracy & Validation Methodology

We verified the pipeline's correctness through automated and manual scenarios:
- **Automated Tests (`tests/test_retrieval.py`)**: Asserts that each sample email correctly routes to the expected plan document and retrieves key numbers.
- **Groundedness Verification**: Run `python -m scripts.run_eval` to draft replies for all 5 sample emails, verifying:
  1. *FSA limit*: Correctly returns the 2026 update of **$3,300**.
  2. *Orthodontics*: Correctly returns the 2022 SMM update of **$2,000** (overriding the older $1,500 base plan limit).
  3. *Travel*: Correctly extracts qualifying lodging/transportation rules.
  4. *Critical illness*: Correctly notes the 2026 Securian admin carrier change.
  5. *LTC enroll*: Correctly flags the plan's closed status (closed in 2019/2020) and outputs a closed draft status rather than enrollment steps.
- **Nonsense Query Bypass**: Verified that queries like *"What is the capital of France?"* trigger the Validation Gate, bypassing the LLM and returning a clean "not found" fallback draft.
- **Overlapping Plan Check**: Querying *"My daughter needs braces while traveling"* retrieves candidates from both **`Dental PPO`** and **`Medical PPO (UHC)`** plans.
- **Conflicting Policy Versions Check**: Verified that when a policy conflict query is run, retrieval returns both versions and the newer policy is selected based on its effective date.

---

## 5. Future Work Roadmap

- **Cross-Encoder Reranking**: Refine candidates using a model like `BAAI/bge-reranker-base` to narrow citations.
- **Multi-Question Decomposition**: Split compound employee questions into separate sub-queries, retrieving and merging candidates individually.
- **Richer Metadata Extraction**: Structurally parse PDF layouts to capture exact sections and effective dates instead of relying on regex heuristics.

---

## 6. Quick Start

### 1. Start Backend FastAPI Server
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # Add Groq API Key under OPENAI_API_KEY
python -m scripts.build_index         # Parse PDFs and generate index
python -m tests.test_retrieval        # Run retrieval routing checks
uvicorn app.main:app --reload
```
Expose the FastAPI port to the web:
```bash
ngrok http 8000 
or 
npx localtunnel --port 8000
```

### 2. Deploy Gmail Add-on UI
```bash
cd addon
clasp login
clasp create --type standalone --title "sigfy benefits assistant"
clasp push
```
Open Apps Script editor (`clasp open`) → **Project Settings** → **Script Properties**, and set `BACKEND_URL` to your Ngrok HTTPS URL. Test and install the add-on in Gmail!

---

## Repository Structure

- **`backend/`**: FastAPI service (ingest, retrieval, response generation, tests, and indexing scripts).
- **`addon/`**: Google Apps Script Gmail Add-on UI card layout, forms, and API transport client.
- **`docs/`**: System architecture layered diagram, expected sample outputs, and observation images.
- **`eval/`**: Customer query prompt data structures used as verification evaluation fixtures.
