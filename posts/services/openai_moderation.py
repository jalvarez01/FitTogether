import base64
import json
import logging
import mimetypes
from typing import Any, Dict, Optional, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENAI_CHAT_COMPLETIONS_ENDPOINT = "https://api.openai.com/v1/chat/completions"

# User-friendly messages
USER_MSG_HATE = "Your post was blocked because it may contain hateful or harassing content."
USER_MSG_SEXUAL = "Your post was blocked because it may contain inappropriate sexual content."
USER_MSG_DANGER = "Your post was blocked because it may contain dangerous or harmful content."
USER_MSG_GENERIC = "Your post was blocked because it violates our community guidelines."
USER_MSG_EMPTY = "Your post must have some content - either text or an image."
USER_MSG_BLOCKED_TERM = "Your post contains a term that is not allowed."
USER_MSG_PENDING = "Your post was saved and is waiting to be moderated. It will be visible to others once approved."

# Result states
APPROVED = "approved"
REJECTED = "rejected"
PENDING = "pending"


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
    logger.warning("Moderation unavailable (post saved as pending): %s", internal_reason)
    return PENDING, USER_MSG_PENDING


def _friendly_rejection(reason_raw: str) -> Tuple[str, str]:
    reason_lower = (reason_raw or "").lower()

    if any(w in reason_lower for w in ("hate", "harassment", "discriminat", "insult", "offensive")):
        return REJECTED, USER_MSG_HATE
    if any(w in reason_lower for w in ("sexual", "explicit", "nude", "nsfw")):
        return REJECTED, USER_MSG_SEXUAL
    if any(w in reason_lower for w in ("danger", "harm", "self-harm", "violence", "illegal", "drug")):
        return REJECTED, USER_MSG_DANGER
    return REJECTED, USER_MSG_GENERIC


def moderate_post(content: str, image_file=None, *, timeout_s: int = 20) -> Tuple[str, str]:
    """
    Returns (status, message), where status is:
    - approved -> post is published normally
    - rejected -> post is blocked, message includes user-friendly reason
    - pending  -> API unavailable, post is stored pending moderation
    """
    api_key = (getattr(settings, "OPENAI_API_KEY", "") or "").strip()
    model = (getattr(settings, "OPENAI_MODEL_TEXT", "gpt-4o-mini") or "").strip()

    text = (content or "").strip()
    if not text and not image_file:
        return REJECTED, USER_MSG_EMPTY

    # No API key means no moderation decisions are made in-app.
    if not api_key:
        return _mark_pending("OPENAI_API_KEY not configured")

    blocked_terms = ["nigga", "nigger", "porn", "xxx", "sex", "fuck you die"]
    for term in blocked_terms:
        if term in text.lower():
            return REJECTED, USER_MSG_BLOCKED_TERM

    moderation_rules = (
        "You are FitTogether Moderation. Decide if a post is allowed. "
        "Hard rules (ALWAYS BLOCK): if text contains blocked terms (exact or obvious variants): "
        f"{blocked_terms}. "
        "Also BLOCK if content includes hate/harassment, sexual content involving minors, explicit sexual content, "
        "self-harm instructions, illegal wrongdoing instructions, insults/profanity/abusive language directed at others. "
        "Return JSON only with this schema: {\"allow\": true|false, \"reason\": \"short_reason\"}. "
        "Keep reason under 60 chars."
    )   

    user_parts = []
    if text:
        user_parts.append({"type": "text", "text": f"USER_POST_TEXT:\n{text}"})

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
        user_parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        )

    payload = {
        "model": model,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": moderation_rules},
            {"role": "user", "content": user_parts or [{"type": "text", "text": "No text provided."}]},
        ],
    }

    try:
        r = requests.post(
            OPENAI_CHAT_COMPLETIONS_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_s,
        )
    except requests.RequestException as e:
        return _mark_pending(f"Network error: {e}")

    if r.status_code != 200:
        return _mark_pending(f"API returned status {r.status_code}")

    try:
        data = r.json()
    except Exception:
        return _mark_pending("API returned non-JSON response")

    choices = data.get("choices") or []
    if not choices:
        return _mark_pending("API returned no choices")

    message = (choices[0] or {}).get("message") or {}
    text_out = (message.get("content") or "").strip()
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

    reason_raw = parsed.get("reason") or ""
    return _friendly_rejection(reason_raw)