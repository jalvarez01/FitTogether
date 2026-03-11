import base64
import json
import mimetypes
import re
from typing import Tuple, Optional, Dict, Any

import requests
from django.conf import settings

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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

    # Busca el primer bloque JSON balanceado
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    # Si quedó incompleto, devolvemos desde el primer "{"
    return s[start:]


def _parse_json_maybe_truncated(raw: str) -> Optional[Dict[str, Any]]:
    cleaned = _strip_code_fences(raw)

    # 1) intento directo
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2) extraer primer objeto JSON
    json_str = _extract_first_json_object(cleaned)
    if not json_str:
        return None

    # 3) parse
    try:
        return json.loads(json_str)
    except Exception:
        pass

    # 4) si está cortado, cerramos llaves
    if json_str.count("{") > json_str.count("}"):
        fixed = json_str + ("}" * (json_str.count("{") - json_str.count("}")))
        try:
            return json.loads(fixed)
        except Exception:
            return None

    return None


def moderate_post(content: str, image_file=None, *, timeout_s: int = 15) -> Tuple[bool, str]:
    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    model = (getattr(settings, "GEMINI_MODEL_TEXT", "gemini-2.5-flash") or "").strip()

    if not api_key:
        return False, "Moderation service is not configured (missing GEMINI_API_KEY)."

    text = (content or "").strip()
    if not text and not image_file:
        return False, "Post is empty."

    # Hard local rule para pruebas: SIEMPRE bloquea melocoton
    if "melocoton" in text.lower():
        return False, "Blocked term: melocoton (testing rule)."

    blocked_terms = ["melocoton"]

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
        "- Illegal wrongdoing instructions\n\n"
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

        # devolver puntero
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
    except requests.RequestException:
        return False, "Moderation service is unavailable. Try again."

    if r.status_code != 200:
        return False, "Moderation service error ({}): {}".format(r.status_code, r.text[:300])

    data = r.json()

    # Prompt bloqueado antes de generar
    prompt_feedback = data.get("promptFeedback") or {}
    if prompt_feedback.get("blockReason"):
        return False, "Post blocked by safety filters (prompt blocked)."

    candidates = data.get("candidates") or []
    if not candidates:
        return False, "Post blocked by safety filters (no candidates)."

    c0 = candidates[0] or {}

    # Candidate bloqueado por SAFETY / RECITATION
    finish_reason = (c0.get("finishReason") or "").upper()
    if finish_reason in {"SAFETY", "RECITATION"}:
        return False, "Post blocked by safety filters ({})".format(finish_reason.lower())

    #  leer texto si existe
    content_obj = c0.get("content") or {}
    parts_out = content_obj.get("parts") or []
    text_out = "".join(p.get("text", "") for p in parts_out).strip()

    if not text_out:
        safety_ratings = c0.get("safetyRatings") or []
        if safety_ratings:
            return False, "Post blocked by safety filters (no output)."
        return False, "Moderation service returned an empty response."

    # Parse robusto del JSON (aunque venga truncado)
    parsed = _parse_json_maybe_truncated(text_out)
    if not parsed:
        preview = _strip_code_fences(text_out)[:200].replace("\n", " ")
        return False, "Moderation service returned an invalid response: {}".format(preview)

    allow_value = parsed.get("allow", parsed.get("allowed", None))
    if allow_value is None:
        preview = _strip_code_fences(text_out)[:200].replace("\n", " ")
        return False, "Moderation service returned an invalid response (missing allow/allowed): {}".format(preview)

    allow = bool(allow_value)
    reason = (parsed.get("reason") or "").strip() or ("OK" if allow else "Not allowed")

    return (True, "OK") if allow else (False, reason)