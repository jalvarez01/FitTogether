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


def _extract_json_object(s: str) -> Optional[str]:
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

    # incomplete / truncated json
    return s[start:]


def _try_parse_json_maybe_truncated(raw: str) -> Optional[Dict[str, Any]]:
    cleaned = (raw or "").strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    # direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # extract first object
    obj = _extract_json_object(cleaned)
    if not obj:
        return None

    # parse extracted
    try:
        return json.loads(obj)
    except Exception:
        pass

    # if truncated, try closing braces
    if obj.startswith("{") and not obj.rstrip().endswith("}"):
        opens = obj.count("{")
        closes = obj.count("}")
        missing = max(0, opens - closes)
        fixed = obj + ("}" * missing)
        try:
            return json.loads(fixed)
        except Exception:
            return None

    return None


def moderate_post(content: str, image_file=None, *, timeout_s: int = 15) -> Tuple[bool, str]:
    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    model = (getattr(settings, "GEMINI_MODEL_TEXT", "gemini-2.0-flash") or "").strip()

    if not api_key:
        return False, "Moderation service is not configured (missing GEMINI_API_KEY)."

    text = (content or "").strip()
    if not text and not image_file:
        return False, "Post is empty."

    # hard local rule (testing)
    if "melocoton" in text.lower():
        return False, "Blocked term: melocoton (testing rule)."

    blocked_terms = ["melocoton"]

    moderation_prompt = (
        "Return ONLY JSON. No markdown. No extra text.\n"
        'Schema: {"allow": true/false, "reason": "short"}\n'
        f"Hard-block terms: {blocked_terms}\n"
        "Block also for: hate/harassment, sexual content (esp minors), explicit sex, self-harm instructions, illegal wrongdoing instructions.\n"
        "Keep reason under 60 chars.\n"
    )

    parts = [{"text": moderation_prompt}]
    if text:
        parts.append({"text": text})

    if image_file:
        try:
            pos = image_file.tell()
        except Exception:
            pos = None

        raw = image_file.read()
        if pos is not None:
            try:
                image_file.seek(pos)
            except Exception:
                pass
        else:
            try:
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
        parts.append({"text": "Apply the same rules to the image."})

    payload = {
        "safetySettings": _safe_settings(),
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 256,
            "stopSequences": ["}\n", "}"],
        },
    }

    url = GEMINI_ENDPOINT.format(model=model)

    try:
        r = requests.post(
            url,
            json=payload,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            timeout=timeout_s,
        )
    except requests.RequestException:
        return False, "Moderation service is unavailable. Try again."

    if r.status_code != 200:
        return False, "Moderation service error ({}): {}".format(r.status_code, r.text[:300])

    data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return False, "Post blocked by safety filters."

    parts_out = (((candidates[0].get("content") or {}).get("parts")) or [])
    text_out = "".join(p.get("text", "") for p in parts_out).strip()
    if not text_out:
        return False, "Post blocked by safety filters (empty model output)."

    parsed = _try_parse_json_maybe_truncated(text_out)
    if not parsed:
        preview = text_out[:200].replace("\n", " ")
        return False, "Moderation service returned an invalid response: {}".format(preview)

    allow_value = parsed.get("allow", parsed.get("allowed", None))
    if allow_value is None:
        preview = text_out[:200].replace("\n", " ")
        return False, "Moderation service returned an invalid response (missing allow): {}".format(preview)

    allow = bool(allow_value)
    reason = (parsed.get("reason") or "").strip() or ("OK" if allow else "Not allowed")

    if allow:
        return True, "OK"
    return False, reason