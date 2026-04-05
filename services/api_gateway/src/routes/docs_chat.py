"""Documentation chatbot endpoint using RAG over Viking-indexed docs.

Flow: user question → Viking semantic search → retrieve top chunks →
construct prompt with context → stream Claude response via SSE.
"""

import json
import os
import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from libs.observability import get_logger
from ..docs_search import search_docs, read_doc_content, uri_to_doc_slug

logger = get_logger("api-gateway.docs-chat")

# Load .env from project root to pick up ANTHROPIC_API_KEY (not PRAXIS_ prefixed)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env"))

router = APIRouter(tags=["docs-chat"])

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are the Praxis Trading Platform documentation assistant. Your job is to help users understand the platform by answering questions based on the provided documentation context.

Rules:
- Answer based ONLY on the provided documentation context. Do not make up information.
- If the answer is not in the context, say "I don't have enough information in the docs to answer that" and suggest which documentation section might be relevant.
- Always cite your sources using markdown links: [Document Title](/docs/slug).
- Keep answers concise but thorough. Use markdown formatting for readability.
- When referencing code paths or files, use backtick formatting.
- If the user asks about something that spans multiple documents, synthesize the information and cite all relevant sources."""


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list[ChatMessage]] = None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat")
async def docs_chat(body: ChatRequest):
    """RAG chat endpoint — searches docs, retrieves context, streams Claude response.

    Emits SSE progress events so the frontend can show each pipeline stage:
      {type: "status", stage: "searching"|"reading"|"generating", message: "..."}
      {type: "sources", sources: [{slug, score, snippet}]}
      {type: "text", text: "..."}
      {type: "done"}
      {type: "error", error: "..."}
    """
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not configured")
        return StreamingResponse(
            iter([_sse({"type": "error", "error": "ANTHROPIC_API_KEY not configured on server"})]),
            media_type="text/event-stream",
        )

    async def stream_response():
        # --- Stage 1: Search ---
        yield _sse({"type": "status", "stage": "searching", "message": "Searching documentation..."})

        results = await search_docs(body.message, top_k=5)
        relevant = [r for r in results if r.score >= 0.4]

        if not relevant:
            yield _sse({"type": "status", "stage": "searching", "message": "No relevant docs found, trying broader search..."})
            relevant = results[:3]  # Use top 3 regardless of score

        yield _sse({
            "type": "status",
            "stage": "searching",
            "message": f"Found {len(relevant)} relevant section{'s' if len(relevant) != 1 else ''}",
        })

        # --- Stage 2: Read docs from disk (instant, no subprocess) ---
        yield _sse({"type": "status", "stage": "reading", "message": "Reading documentation..."})

        context_parts = []
        sources = []
        for result in relevant:
            content = read_doc_content(result)
            if content:
                slug = uri_to_doc_slug(result.uri)
                source_label = slug or result.uri
                context_parts.append(f"### Source: {source_label}\n{content}")
                source_entry = {
                    "slug": slug or source_label,
                    "score": round(result.score, 3),
                    "snippet": result.snippet[:120] if result.snippet else "",
                }
                sources.append(source_entry)
                yield _sse({
                    "type": "status",
                    "stage": "reading",
                    "message": f"Read: {slug or source_label}",
                })

        # Send sources to frontend
        if sources:
            yield _sse({"type": "sources", "sources": sources})

        context_text = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documentation found."

        # --- Stage 3: Generate ---
        yield _sse({"type": "status", "stage": "generating", "message": "Generating answer..."})

        messages = []
        if body.history:
            for msg in body.history[-6:]:
                messages.append({"role": msg.role, "content": msg.content})

        user_content = f"""## Relevant Documentation
{context_text}

## Question
{body.message}"""
        messages.append({"role": "user", "content": user_content})

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": ANTHROPIC_MODEL,
                        "max_tokens": 2048,
                        "system": SYSTEM_PROMPT,
                        "messages": messages,
                        "stream": True,
                    },
                    timeout=60.0,
                ) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        error_text = error_body.decode()
                        logger.error("Claude API error", status=resp.status_code, body=error_text)
                        yield _sse({"type": "error", "error": f"Claude API returned {resp.status_code}: {error_text[:200]}"})
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield _sse({"type": "text", "text": delta.get("text", "")})
                            elif event.get("type") == "message_stop":
                                break
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException:
            yield _sse({"type": "error", "error": "Request timed out. Please try again."})
            return
        except Exception as e:
            logger.error("Streaming error", error=str(e))
            yield _sse({"type": "error", "error": "An internal error occurred. Please try again."})
            return

        yield _sse({"type": "done"})

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
