---
title: sigfy
emoji: 🚀
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Sigfy: AI Benefits Email Assistant

An intelligent Gmail Workspace Add-on backed by a FastAPI Retrieval-Augmented Generation (RAG) backend. It helps benefits managers draft fast, grounded, and citation-backed replies using plan documents.

---

## Quick Access Links
* **Live Backend API (Hugging Face):** [https://huggingface.co/spaces/rshalvi/sigfy](https://huggingface.co/spaces/rshalvi/sigfy)
* **GitHub Repository:** [https://github.com/shalvirajpura2/sigfy](https://github.com/shalvirajpura2/sigfy)
* **View Draft Screenshots:** [sample-outputs.md](docs/sample-outputs.md) *(See screenshots of the Gmail Add-on UI drafting replies)*
* **Architecture Diagram & Details:** [ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Table of Contents
1. [How It Works (Retrieval & Drafting)](#1-how-it-works-retrieval--drafting)
2. [Key Design Choices](#2-key-design-choices)
3. [Challenges & Solutions](#3-challenges--solutions)
4. [How We Verify Accuracy](#4-how-we-verify-accuracy)
5. [Setup & Running Instructions](#5-setup--running-instructions)
6. [Testing the API (cURL Examples)](#6-testing-the-api-curl-examples)

---

## 1. How It Works (Retrieval & Drafting)

Instead of feeding whole PDF documents into the AI (which is slow and expensive), Sigfy extracts only the most relevant sections before drafting replies:

1. **Pre-computing Search Files (Offline Ingestion)**: Plan PDFs are split into clean, short paragraphs. We pre-generate mathematical coordinates (embeddings) for these paragraphs using a local model (`bge-small-en-v1.5`) and cache them. This lets the backend search hundreds of pages in under 15 milliseconds on a normal CPU.
2. **Context-Aware Smart Filter**: When an email arrives, the query is scanned for keywords. If it's about braces, it targets the dental plan. If it's general, it searches the entire library.
3. **Keyword & Meaning Search (Hybrid Retrieval)**: We search the paragraphs using both traditional keyword matching (BM25) and conceptual meaning matching (dense vector search) to find the best paragraphs.
4. **Confidence Signal (Evidence Gate)**: The top matching paragraph's score is evaluated. If it's a weak match, we flag the response as low-confidence and alert the user with a `[Low evidence]` note.
5. **Grounded Reply Generation**: The AI writes a friendly draft reply using **only** the retrieved paragraphs. If multiple document versions exist, the AI compares effective dates and selects the newest rule.

---

## 2. Key Design Choices

* **Prioritizing Keywords over Meanings (Lexical Bias)**: In insurance documents, exact terms (like "$3,300" or plan names) are much more important than abstract meanings. We prioritize keyword matching to ensure the correct numbers are always selected.
* **Metadata Scope Filtering**: Restricting searches to matching plan documents (like the Dental PDF for orthodontic questions) prevents irrelevant details in other files from corrupting the AI's response.
* **Async Batch Processing**: Benefits coordinators receive hundreds of emails. The backend supports asynchronous batching: users send a batch request, get a task ID instantly, and let the backend process replies in the background without blocking the UI.
* **Privacy-First Console Logging**: We never print email bodies or names to the logs. We use anonymous request hashes to trace query latency and search performance safely.

---

## 3. Challenges & Solutions

### Overlapping Vocabularies & Outdated Rules
**Challenge**: Plan documents from different years have overlapping keywords. A naive search might pull an outdated orthodontic limit from a 2019 plan instead of the active 2022 limit.

**Solution**:
1. We parse and index the **effective date** of every document section.
2. If the retriever pulls multiple matching policies, the AI is instructed to look at the effective dates, discard older limits, and explicitly mention in the notes that the older policy has been updated.
3. We added a confidence filter that overrides the AI's output and marks it as low-confidence if the matches are weak.

---

## 4. How We Verify Accuracy

We verify the correctness of the assistant using 5 real email scenarios representing complex edge cases:

1. **FSA Limits (2026 Change)**: The AI correctly identifies that the Health FSA limit has increased to **$3,300** (from $3,200) for 2026, citing the new plan document.
2. **Orthodontics (Network vs. Out-of-Network)**: The AI accurately pulls the lifetime limits of **$2,000** (in-network) and **$1,000** (out-of-network) from the newer SMM update.
3. **Travel Reimbursement for Specialists**: The AI extracts the rule that the specialist must be over 100 miles away to qualify for lodging/transportation coverage.
4. **Carrier Administrator Changes**: The AI correctly identifies that Securian has taken over Critical Illness claims from Aflac starting 2026 and notifies the employee that their coverage carries over automatically.
5. **Closed Plan Request (Long-Term Care)**: The employee asks to enroll in Long-Term Care. The AI identifies that the plan closed to new enrollees in 2019, marks the response as low-confidence (`found=false`), and drafts a polite response explaining that enrollment is no longer possible.
6. **Nonsense Query Handling**: If an employee asks an unrelated question (e.g., *"What is the capital of France?"*), the system filters it out or marks it as "not found" instead of guessing or fabricating an answer.

---

## 5. Setup & Running Instructions

### Backend Server (FastAPI)
You can run the backend server locally inside a Python virtual environment:

```bash
# 1. Clone and navigate to backend
cd backend

# 2. Set up virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env           # Open .env and add your Groq/OpenAI API key

# 5. Build the search index
python -m scripts.build_index

# 6. Run the server
uvicorn app.main:app --reload
```

*To deploy the server to the web, you can use ngrok: `ngrok http 8000` or localtunnel: `npx localtunnel --port 8000`.*

### Gmail Add-on UI (Google Apps Script)
```bash
cd addon
clasp login
clasp create --type standalone --title "sigfy benefits assistant"
clasp push
```
1. Open the Apps Script project URL printed by Clasp.
2. Go to **Project Settings** ➔ **Script Properties**.
3. Add `BACKEND_URL` and set its value to your public FastAPI server URL.
4. Add `API_KEY` (if your server requires shared-secret authentication).
5. Click **Deploy** ➔ **Test Deployments** ➔ **Install** to add it to your Gmail sidebar.

---

## 6. Testing the API (cURL Examples)

You can check if the API is active and testing correctly using these commands:

### Check Health & Data Index
```bash
curl -X GET https://rshalvi-sigfy.hf.space/health
```

### Request a Draft Reply
```bash
curl -X POST https://rshalvi-sigfy.hf.space/draft \
     -H "Content-Type: application/json" \
     -d '{
           "subject": "FSA contribution question",
           "sender": "jmartinez@company.com",
           "receiver": "jmartinez@company.com",
           "body": "Hi, I thought the max I could put into my Health FSA was $3,200. Is that correct for 2026?",
           "debug": false
         }'
```

### Request an Async Batch Draft
```bash
curl -X POST https://rshalvi-sigfy.hf.space/batch_draft_async \
     -H "Content-Type: application/json" \
     -d '{
           "requests": [
             {
               "subject": "FSA Limit",
               "sender": "j@company.com",
               "receiver": "j@company.com",
               "body": "What is the FSA limit for 2026?"
             }
           ]
         }'
```
*(Copy the `task_id` from the response and check status at `https://rshalvi-sigfy.hf.space/task_status/<task_id>`)*
