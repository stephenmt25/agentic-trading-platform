"""Local SLM Inference Service.

Hosts a quantized GGUF model via llama-cpp-python, exposing:
- POST /v1/completions  — OpenAI-compatible text completion
- POST /v1/sentiment    — Structured sentiment analysis (returns JSON score)
- GET  /health          — Health check with GPU memory and inference latency
"""

import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
import uvicorn


def _register_cuda_dll_dirs() -> None:
    """On Windows, llama-cpp-python's CUDA wheel needs cudart/cublas DLLs to be
    discoverable via os.add_dll_directory(). The NVIDIA pip packages
    (`nvidia-cuda-runtime-cu12`, `nvidia-cublas-cu12`) drop the DLLs into
    `site-packages/nvidia/<lib>/bin`. Silently no-op on non-Windows or when
    the packages are absent (CPU build path).
    """
    if sys.platform != "win32":
        return
    try:
        import nvidia  # type: ignore
    except ImportError:
        return
    # nvidia is a PEP 420 namespace package — its __file__ is None.
    # Walk its __path__ entries (one per installed nvidia-* package).
    # Both PATH prepending and os.add_dll_directory() are needed:
    # add_dll_directory affects DLLs Python loads directly; PATH affects
    # the transitive chain (llama.dll -> ggml-cuda.dll -> cudart/cublas).
    for nvidia_root in map(Path, nvidia.__path__):
        for sub in ("cuda_runtime", "cublas"):
            bin_dir = nvidia_root / sub / "bin"
            if bin_dir.is_dir():
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
                os.add_dll_directory(str(bin_dir))

from libs.config import settings
from libs.core.schemas import CompletionRequest, CompletionResponse, SentimentRequest, SentimentResponse
from libs.observability import get_logger

logger = get_logger("slm-inference")

# Global model reference (loaded at startup)
_llm = None
_model_info = {"model_path": "", "loaded": False, "load_time_ms": 0}


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _load_model():
    """Load the GGUF model. Imports llama-cpp-python lazily."""
    global _llm
    model_path = settings.SLM_MODEL_PATH
    if not model_path:
        logger.warning("SLM_MODEL_PATH not set — inference will use mock responses")
        return

    try:
        _register_cuda_dll_dirs()
        from llama_cpp import Llama

        start = time.monotonic()
        _llm = Llama(
            model_path=model_path,
            n_ctx=settings.SLM_CONTEXT_LENGTH,
            n_gpu_layers=settings.SLM_GPU_LAYERS,
            verbose=False,
        )
        load_time = (time.monotonic() - start) * 1000
        _model_info["model_path"] = model_path
        _model_info["loaded"] = True
        _model_info["load_time_ms"] = load_time
        logger.info("SLM model loaded", model_path=model_path, load_time_ms=f"{load_time:.0f}")
    except ImportError:
        logger.error("llama-cpp-python not installed — run: pip install llama-cpp-python")
    except Exception as e:
        logger.error("Failed to load SLM model", error=str(e), model_path=model_path)


def _generate(prompt: str, max_tokens: int = 256, temperature: float = 0.1,
              stop: Optional[list[str]] = None, grammar: Optional[str] = None) -> tuple[str, int]:
    """Generate text from the loaded model via its bundled chat template.

    Uses ``create_chat_completion()`` so the model's own chat template
    (e.g. Phi-3's ``<|user|>...<|assistant|>``) is applied — chat-tuned models
    follow instructions far more reliably with their native template than with
    raw completion. If grammar (GBNF) is provided, output is constrained to
    match it.
    """
    if _llm is None:
        # Mock response for development without a model
        return '{"score": 0.0, "confidence": 0.3}', 10

    kwargs: dict = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop": stop or [],
    }
    if grammar:
        from llama_cpp import LlamaGrammar
        kwargs["grammar"] = LlamaGrammar.from_string(grammar, verbose=False)

    output = _llm.create_chat_completion(**kwargs)
    text = output["choices"][0]["message"]["content"]
    tokens = output["usage"]["total_tokens"]
    return text, tokens


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_model()
    logger.info("SLM Inference Service started")
    yield
    logger.info("SLM Inference Service shutdown")


app = FastAPI(title="SLM Inference Service", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/v1/completions", response_model=CompletionResponse)
async def completions(req: CompletionRequest):
    start = time.monotonic()
    try:
        text, tokens = _generate(req.prompt, req.max_tokens, req.temperature, req.stop, req.grammar)
    except Exception as e:
        logger.error("Inference error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal inference error")
    latency = (time.monotonic() - start) * 1000

    return CompletionResponse(text=text, tokens_used=tokens, latency_ms=round(latency, 1))


@app.post("/v1/sentiment", response_model=SentimentResponse)
async def sentiment(req: SentimentRequest):
    if not req.headlines:
        return SentimentResponse(score=0.0, confidence=0.1, latency_ms=0.0)

    prompt = (
        f"Analyze the market sentiment for {req.symbol} based on these headlines:\n"
        + "\n".join(f"- {h[:200]}" for h in req.headlines[:5])
        + "\n\nYou MUST respond with ONLY raw valid JSON (no markdown, no extra text).\n"
        + 'Respond with exactly: {"score": <float -1.0 to 1.0>, "confidence": <float 0.0 to 1.0>}'
    )

    start = time.monotonic()
    try:
        text, _ = _generate(prompt, max_tokens=100, temperature=0.1, stop=["\n\n"])
    except Exception as e:
        logger.error("Inference error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal inference error")
    latency = (time.monotonic() - start) * 1000

    # Parse structured output
    try:
        # Try to find JSON in the response
        text = text.strip()
        if not text.startswith("{"):
            # Find first { in response
            idx = text.find("{")
            if idx >= 0:
                text = text[idx:]
        parsed = json.loads(text)
        score = max(-1.0, min(1.0, float(parsed["score"])))
        confidence = max(0.0, min(1.0, float(parsed["confidence"])))
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.warning("Failed to parse SLM sentiment response", raw=text[:200])
        score = 0.0
        confidence = 0.3

    return SentimentResponse(score=score, confidence=confidence, latency_ms=round(latency, 1))


@app.get("/health")
def health():
    info = {
        "status": "healthy",
        "model_loaded": _model_info["loaded"],
        "model_path": _model_info["model_path"],
        "load_time_ms": _model_info["load_time_ms"],
    }

    # GPU memory info if available
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu_memory_allocated_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 1)
            info["gpu_memory_reserved_mb"] = round(torch.cuda.memory_reserved() / 1024 / 1024, 1)
    except ImportError:
        pass

    return info


if __name__ == "__main__":
    uvicorn.run("services.slm_inference.src.main:app", host="0.0.0.0", port=8095)
