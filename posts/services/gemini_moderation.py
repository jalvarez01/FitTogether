import base64
import json
import logging
import mimetypes
from typing import Tuple, Optional, Dict, Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# ── Mensajes amigables ──────────────────────────────────────────────────────
USER_MSG_HATE = "Your post was blocked because it may contain hateful or harassing content."
USER_MSG_SEXUAL = "Your post was blocked because it may contain inappropriate sexual content."
USER_MSG_DANGER = "Your post was blocked because it may contain dangerous or harmful content."
USER_MSG_GENERIC = "Your post was blocked because it violates our community guidelines."
USER_MSG_EMPTY = "Your post must have some content — either text or an image."
USER_MSG_BLOCKED_TERM = "Your post contains a term that is not allowed."
USER_MSG_PENDING = "Your post was saved and is waiting to be moderated. It will be visible to others once approved."

# Estados posibles
APPROVED = "approved"
REJECTED = "rejected"
PENDING = "pending"


def _safe_settings():
    return [
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]


def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    return s


def _extract_first_json_object(s: str) -> Optional[str]:
    s = (s or "").strip()
    start = s.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    return s[start:]


def _parse_json_maybe_truncated(raw: str) -> Optional[Dict[str, Any]]:
    cleaned = _strip_code_fences(raw)

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    json_str = _extract_first_json_object(cleaned)
    if not json_str:
        return None

    try:
        return json.loads(json_str)
    except Exception:
        pass

    if json_str.count("{") > json_str.count("}"):
        fixed = json_str + ("}" * (json_str.count("{") - json_str.count("}")))
        try:
            return json.loads(fixed)
        except Exception:
            return None

    return None


def _mark_pending(internal_reason: str) -> Tuple[str, str]:
    """API no disponible → el post se guarda como pendiente."""
    logger.warning("Moderation unavailable (post saved as pending): %s", internal_reason)
    return PENDING, USER_MSG_PENDING


def _friendly_rejection(reason_raw: str) -> Tuple[str, str]:
    """Traduce la razón de Gemini a un mensaje legible."""
    reason_lower = reason_raw.lower()

    if any(w in reason_lower for w in ("hate", "harassment", "discriminat", "insult", "offensive")):
        return REJECTED, USER_MSG_HATE
    elif any(w in reason_lower for w in ("sexual", "explicit", "nude", "nsfw")):
        return REJECTED, USER_MSG_SEXUAL
    elif any(w in reason_lower for w in ("danger", "harm", "self-harm", "violence", "illegal", "drug")):
        return REJECTED, USER_MSG_DANGER
    else:
        return REJECTED, USER_MSG_GENERIC


def moderate_post(content: str, image_file=None, *, timeout_s: int = 15) -> Tuple[str, str]:
    """
    Retorna (status, message) donde status es:
    - "approved"  → el post se publica normalmente
    - "rejected"  → el post se bloquea, message tiene la razón amigable
    - "pending"   → la API no respondió, el post se guarda pendiente de moderación
    """
    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    model = (getattr(settings, "GEMINI_MODEL_TEXT", "gemini-2.5-flash") or "").strip()

    text = (content or "").strip()
    if not text and not image_file:
        return REJECTED, USER_MSG_EMPTY

    # ── Reglas locales (no dependen de la API) ──────────────────────────────
    blocked_terms = ["melocoton"]
    for term in blocked_terms:
        if term in text.lower():
            return REJECTED, USER_MSG_BLOCKED_TERM

    # ── Sin API key → pendiente ─────────────────────────────────────────────
    if not api_key:
        return _mark_pending("GEMINI_API_KEY not configured")

    # ── Construir request a Gemini ──────────────────────────────────────────
    moderation_prompt = (
        "You are FitTogether Moderation.\n"
        "Decide if a post is allowed.\n\n"
        "Hard rules (ALWAYS BLOCK):\n"
        f"- If the text contains any of these blocked terms (exact or obvious variants): {blocked_terms}\n\n"
        "Also BLOCK if content includes:\n"
        "- Hate/harassment\n"
        "- Sexual content involving minors\n"
        "- Explicit sexual content\n"
        "- Self-harm instructions\n"
        "- Illegal wrongdoing instructions\n"
        "- Insults, profanity, or abusive language directed at others\n\n"
        "Return ONLY JSON in ONE LINE (no markdown/backticks):\n"
        '{"allow": true/false, "reason": "short_reason"}\n'
        "Keep reason under 60 chars.\n"
    )

    parts = [{"text": moderation_prompt}]
    if text:
        parts.append({"text": f"USER_POST_TEXT:\n{text}"})

    if image_file:
        try:
            pos = image_file.tell()
        except Exception:
            pos = None

        raw = image_file.read()

        try:
            if pos is not None:
                image_file.seek(pos)
            else:
                image_file.seek(0)
        except Exception:
            pass

        mime = (
            getattr(image_file, "content_type", None)
            or mimetypes.guess_type(getattr(image_file, "name", ""))[0]
            or "image/jpeg"
        )
        b64 = base64.b64encode(raw).decode("utf-8")
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
        parts.append({"text": "USER_POST_IMAGE: Apply the same rules to the image."})

    payload = {
        "safetySettings": _safe_settings(),
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 256,
        },
        "contents": [{"role": "user", "parts": parts}],
    }

    url = GEMINI_ENDPOINT.format(model=model)

    # ── Llamar a la API ─────────────────────────────────────────────────────
    try:
        r = requests.post(
            url,
            json=payload,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout_s,
        )
    except requests.RequestException as e:
        return _mark_pending(f"Network error: {e}")

    if r.status_code != 200:
        return _mark_pending(f"API returned status {r.status_code}")

    # ── Parsear respuesta ───────────────────────────────────────────────────
    try:
        data = r.json()
    except Exception:
        return _mark_pending("API returned non-JSON response")

    prompt_feedback = data.get("promptFeedback") or {}
    if prompt_feedback.get("blockReason"):
        return REJECTED, USER_MSG_GENERIC

    candidates = data.get("candidates") or []
    if not candidates:
        return REJECTED, USER_MSG_GENERIC

    c0 = candidates[0] or {}

    finish_reason = (c0.get("finishReason") or "").upper()
    if finish_reason in {"SAFETY", "RECITATION"}:
        return REJECTED, USER_MSG_GENERIC

    content_obj = c0.get("content") or {}
    parts_out = content_obj.get("parts") or []
    text_out = "".join(p.get("text", "") for p in parts_out).strip()

    if not text_out:
        return _mark_pending("API returned empty text output")

    parsed = _parse_json_maybe_truncated(text_out)
    if not parsed:
        return _mark_pending(f"API returned unparseable JSON: {text_out[:200]}")

    allow_value = parsed.get("allow", parsed.get("allowed", None))
    if allow_value is None:
        return _mark_pending(f"API JSON missing 'allow' key: {text_out[:200]}")

    if bool(allow_value):
        return APPROVED, "OK"

    # ── Rechazado por Gemini → mensaje amigable ─────────────────────────────
    reason_raw = parsed.get("reason") or ""
    return _friendly_rejection(reason_raw)