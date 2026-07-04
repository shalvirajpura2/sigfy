from __future__ import annotations

import json
import re

from .config import settings
from .models import Citation, DraftResponse, RetrievedChunk

SYSTEM_PROMPT = """you are an assistant for a benefits account manager. an employee \
has emailed a question about their benefits. draft a reply for the account manager to \
review, edit, and send.

hard rules:
- answer only using the numbered sources provided. never use outside knowledge or \
assumptions about what a plan "usually" covers.
- ground every factual claim (dollar amounts, limits, rules, steps) in a source.
- when sources disagree because of plan updates, prefer the one with the most recent \
effective date and briefly note that an earlier value was superseded.
- watch dates against today's date: if the employee wants to do something \
time-sensitive (enroll, elect, file) and the sources show that window has passed, or \
the plan has closed to new participants (for example, the plan closed after October 13, 2019), \
set found=false and draft a reply that plainly explains that the plan closed to new enrollees as of that date, \
and that the requested enrollment is no longer possible. Assume any enrollment windows or deadlines in the \
past (e.g., 2019, 2020) are expired and closed relative to today's date, and do not imply they might still be open. \
Do NOT write a generic "confirming details and will follow up" draft when the plan or enrollment windows are shown as closed or expired.
- if the sources do not clearly and specifically answer the question (and the plan is not shown as closed or expired), set found=false, \
do not guess, and write a short draft that says you're confirming the details and will \
follow up (never invent an answer to seem helpful).
- keep the draft warm, plain, and concise. no legalese. do not fabricate names, phone \
numbers, or links that are not in the sources.

return ONLY a JSON object, no prose around it, with this shape:
{
  "found": true | false,
  "confidence": "high" | "medium" | "low",
  "draft": "the full reply email body, ready to edit and send",
  "citations": [
    {"source": 1, "quote": "short verbatim snippet you relied on"}
  ],
  "notes": "conflicts, superseded values, or assumptions the manager should know (may be empty)"
}
confidence is high only when one or more sources directly and unambiguously answer the \
question. use low when the match is weak or partial."""


def build_context(chunks: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(chunks, start=1):
        header = f"[source {i}] document: {c['document']}"
        if c.get("section"):
            header += f" | section: {c['section']}"
        if c.get("page"):
            header += f" | page: {c['page']}"
        if c.get("effective_date"):
            header += f" | effective: {c['effective_date']}"
        blocks.append(f"{header}\n{c['text']}")
    return "\n\n".join(blocks)


def build_user_prompt(subject: str, sender: str, body: str, context: str) -> str:
    from datetime import date

    return (
        f"today's date: {date.today().isoformat()}\n\n"
        f"employee email\nfrom: {sender}\nsubject: {subject}\n\n{body.strip()}\n\n"
        f"---\nnumbered sources (the only information you may use):\n\n{context}"
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("model did not return JSON")
    return json.loads(text[start : end + 1])


def _to_citations(raw: list, chunks: list[dict]) -> list[Citation]:
    citations: list[Citation] = []
    seen = set()
    for item in raw or []:
        idx = item.get("source")
        if not isinstance(idx, int) or not (1 <= idx <= len(chunks)):
            continue
        c = chunks[idx - 1]
        key = (c["document"], c.get("section", ""), c.get("page"))
        if key in seen:
            continue
        seen.add(key)
        citations.append(Citation(
            document=c["document"],
            section=c.get("section", ""),
            page=c.get("page"),
            quote=(item.get("quote") or "").strip()[:280],
            chunk_id=c.get("id", ""),
            effective_date=c.get("effective_date", ""),
            retrieval_score=round(float(c.get("score", 0.0)), 5)
        ))
    return citations


def _retrieved(chunks: list[dict]) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            document=c["document"], section=c.get("section", ""), page=c.get("page"),
            effective_date=c.get("effective_date", ""), score=c.get("score", 0.0),
            text=c["text"][:400],
        )
        for c in chunks
    ]


def _complete_anthropic(user_prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(b.text for b in message.content if b.type == "text")


def _complete_openai(user_prompt: str) -> str:
    from openai import OpenAI
    import logging
    log = logging.getLogger("benefits")

    # Gather candidate API keys
    keys = []
    if settings.groq_api_keys:
        keys.extend(settings.groq_api_keys)
    if settings.openai_api_key:
        keys.append(settings.openai_api_key)

    # Attempt keys in sequence
    last_exception = None
    for idx, key in enumerate(keys):
        try:
            base_url = settings.openai_base_url if settings.openai_base_url else None
            client = OpenAI(api_key=key, base_url=base_url)
            resp = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=settings.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            log.info("LLM call succeeded with API key index %d", idx)
            return resp.choices[0].message.content or ""
        except Exception as e:
            log.warning("API key index %d failed: %s", idx, e)
            last_exception = e

    # Fallback to Gemini if all primary keys failed and a Gemini key is configured
    if settings.gemini_api_key:
        log.info("Attempting fallback to Gemini API (gemini-1.5-flash)...")
        try:
            client = OpenAI(
                api_key=settings.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            resp = client.chat.completions.create(
                model="gemini-1.5-flash",
                max_tokens=settings.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            log.info("LLM call succeeded via Gemini fallback.")
            return resp.choices[0].message.content or ""
        except Exception as gemini_err:
            log.error("Gemini fallback failed: %s", gemini_err)
            raise gemini_err

    if last_exception:
        raise last_exception
    raise RuntimeError("No LLM API keys configured.")


def generate_draft(subject: str, sender: str, body: str, chunks: list[dict],
                   debug: bool = False) -> DraftResponse:
    from .retrieval import validate_evidence

    top_chunk = chunks[0] if chunks else None
    if not validate_evidence(top_chunk):
        return DraftResponse(
            found=False,
            confidence="low",
            draft="I'm confirming the details and will follow up with more information as soon as possible.",
            citations=[],
            notes="Evidence Validation Gate: Insufficient matching passages found in plan documents.",
            model="none (bypass)",
            retrieved=_retrieved(chunks) if debug else [],
        )

    context = build_context(chunks)
    user_prompt = build_user_prompt(subject, sender, body, context)

    if not settings.has_llm:
        return DraftResponse(
            found=False, confidence="low",
            draft="[dry-run] no LLM api key set — showing retrieval only. set "
                  "ANTHROPIC_API_KEY (or OPENAI_API_KEY) to generate a grounded draft.",
            notes="dry-run mode", model="dry-run",
            retrieved=_retrieved(chunks),
        )

    text = (_complete_openai if settings.provider == "openai" else _complete_anthropic)(user_prompt)
    data = _extract_json(text)

    return DraftResponse(
        found=bool(data.get("found", False)),
        confidence=str(data.get("confidence", "medium")).lower(),
        draft=(data.get("draft") or "").strip(),
        citations=_to_citations(data.get("citations", []), chunks),
        notes=(data.get("notes") or "").strip(),
        model=settings.model,
        retrieved=_retrieved(chunks) if debug else [],
    )
