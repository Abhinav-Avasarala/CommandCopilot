"""
llm_fallback.py — LLM-based fix suggestion using a local Phi-2 model (GGUF format).

Only invoked when regex rules in rules.py find no match.

Loading behavior:
  - First call: loads the model from disk (~10 seconds, printed to log)
  - Subsequent calls within the same process: instant (cached in _llm)
  - If the model file is missing or llama-cpp-python is not installed,
    returns None silently so the caller can fall back to the default message.

Model expected at: ~/phi-2.Q4_K_M.gguf  (~1.6 GB)
See INSTRUCTIONS_VCL.md Part 8 for download and scp instructions.
"""

import os
import logging

log = logging.getLogger(__name__)

# ── Model config ───────────────────────────────────────────────────────────────
# Stored in /share (scratch space), NOT ~ (home directory).
# NCSU HPC home dir quota is only 15 GB / 10K files — too small for a 1.6 GB model.
# /share/dsa440s26 has 20 TB and is the correct place for large data files.
MODEL_PATH = "/share/dsa440s26/aavasar/phi-2.Q4_K_M.gguf"
N_THREADS   = 4    # match the 4 CPU cores on the VCL machine
N_CTX       = 512  # small context window — faster inference, enough for error text
MAX_TOKENS  = 80   # fix suggestions are short; stop generating early

# Module-level cache — model loads once per consumer.py process, reused after that
_llm = None


def _load_model():
    """
    Lazily load the Phi-2 GGUF model. Returns the Llama instance or None if
    llama-cpp-python is not installed or the model file is missing.
    """
    global _llm
    if _llm is not None:
        return _llm

    try:
        from llama_cpp import Llama
    except ImportError:
        log.warning("[LLM] llama-cpp-python not installed — LLM fallback disabled.")
        log.warning("[LLM] To enable: see INSTRUCTIONS_VCL.md Part 8.")
        return None

    if not os.path.exists(MODEL_PATH):
        log.warning("[LLM] Model file not found at %s", MODEL_PATH)
        log.warning("[LLM] To enable: scp phi-2.Q4_K_M.gguf to %s", MODEL_PATH)
        log.warning("[LLM] See INSTRUCTIONS_VCL.md Part 8 for full instructions.")
        return None

    log.info("[LLM] First LLM call — loading Phi-2 model from %s ...", MODEL_PATH)
    log.info("[LLM] This takes ~10s. Subsequent calls this session are instant.")
    _llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        verbose=False,    # suppress llama.cpp's own logging noise
    )
    log.info("[LLM] Model ready.")
    return _llm


def get_llm_fix(error_text: str) -> str | None:
    """
    Ask Phi-2 for a fix suggestion for the given error text.

    Returns a non-empty fix string on success, or None if:
      - llama-cpp-python is not installed
      - model file is missing
      - the model returned an empty response

    The caller (rules.py) is responsible for handling the None case.
    """
    llm = _load_model()
    if llm is None:
        return None

    # Trim error to fit context window — first 600 chars covers almost all real errors
    trimmed = error_text[:600].replace('\n', ' ').strip()

    # Phi-2 was fine-tuned on Instruct/Output format
    prompt = (
        "Instruct: You are a terminal error assistant. "
        f'A user got this error: "{trimmed}". '
        "Respond with ONE concise fix: a shell command or a short explanation under 20 words. "
        "Output:"
    )

    result = llm(
        prompt,
        max_tokens=MAX_TOKENS,
        stop=["Instruct:", "\n\n"],  # stop at next prompt or blank line
        echo=False,
    )

    fix = result["choices"][0]["text"].strip()
    return fix if fix else None
