"""
AccessCheck - VLM Audit Agent

Sends images to Gemini Vision for accessibility analysis and
parses structured results back into FiftyOne sample fields.
"""

import json
import logging
import mimetypes
import os
import time

from google import genai
from google.genai import types

from prompts import ACCESSIBILITY_AUDIT_PROMPT

logger = logging.getLogger(__name__)

_GEMINI_CLIENT = None


AUDIT_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "required": ["scene_type", "overall_accessible", "accessibility_score", "issues"],
    "properties": {
        "scene_type": {"type": "string"},
        "overall_accessible": {"type": "boolean"},
        "accessibility_score": {"type": "number", "minimum": 0, "maximum": 100},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "issue_type",
                    "severity",
                    "description",
                    "location_in_image",
                    "remediation",
                    "ada_reference",
                ],
                "properties": {
                    "issue_type": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "major", "minor"],
                    },
                    "description": {"type": "string"},
                    "location_in_image": {"type": "string"},
                    "remediation": {"type": "string"},
                    "ada_reference": {"type": "string"},
                },
            },
        },
    },
}


def configure_gemini(api_key=None):
    """
    Configure Gemini via the latest google-genai SDK.

    Reads from GOOGLE_API_KEY or GEMINI_API_KEY if api_key is not provided.
    """
    global _GEMINI_CLIENT

    key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "Gemini API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY, "
            "or pass api_key parameter."
        )

    _GEMINI_CLIENT = genai.Client(api_key=key)
    logger.info("Gemini client configured (google-genai SDK)")
    return _GEMINI_CLIENT


def _get_gemini_client():
    if _GEMINI_CLIENT is None:
        return configure_gemini()

    return _GEMINI_CLIENT


def _clean_json_text(text):
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_image_part(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/jpeg"

    return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


def _parse_gemini_response(response):
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed

    if parsed is not None:
        # Some schemas may produce non-dict parsed output
        if isinstance(parsed, str):
            return json.loads(_clean_json_text(parsed))
        return parsed

    text = _clean_json_text(getattr(response, "text", ""))
    if not text:
        raise ValueError("Gemini returned an empty response")

    return json.loads(text)


class RateLimitError(Exception):
    """Raised when Gemini API rate limit is hit."""
    def __init__(self, retry_after=60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s.")


def audit_single_image(image_path, model_name="gemini-2.5-flash", max_retries=2):
    """
    Send a single image to Gemini for accessibility audit.

    Args:
        image_path: path to the image file
        model_name: Gemini model to use
        max_retries: number of retries on JSON parse failure

    Returns:
        dict with parsed audit results, or None on failure

    Raises:
        RateLimitError: when Gemini API quota is exhausted
    """
    for attempt in range(max_retries + 1):
        try:
            client = _get_gemini_client()
            image_part = _build_image_part(image_path)

            response = client.models.generate_content(
                model=model_name,
                contents=[ACCESSIBILITY_AUDIT_PROMPT, image_part],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                    response_json_schema=AUDIT_RESPONSE_JSON_SCHEMA,
                ),
            )

            result = _parse_gemini_response(response)
            if not isinstance(result, dict):
                raise ValueError(f"Expected dict result, got {type(result)}")

            issues = result.get("issues")
            if not isinstance(issues, list):
                result["issues"] = []

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error for {image_path} (attempt {attempt+1}): {e}")
            if attempt < max_retries:
                time.sleep(0.5)
                continue
            # Last attempt: try to salvage truncated JSON
            try:
                raw = _clean_json_text(getattr(response, "text", ""))
                result = _repair_truncated_json(raw)
                if result:
                    return result
            except Exception:
                pass
            logger.error(f"Failed to parse JSON for {image_path} after {max_retries+1} attempts")
            return None
        except Exception as e:
            error_str = str(e)
            # Detect rate limiting and propagate it so the server can inform the user
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                retry_after = 60
                # Try to parse retry delay from error message
                import re
                match = re.search(r"retry\s*in\s*([\d.]+)", error_str, re.IGNORECASE)
                if match:
                    retry_after = int(float(match.group(1))) + 1
                raise RateLimitError(retry_after)
            logger.error(f"Error auditing {image_path}: {e}", exc_info=True)
            return None

    return None


def _repair_truncated_json(raw):
    """
    Attempt to salvage a truncated JSON response from Gemini.
    Tries to close open strings, arrays, and objects.
    """
    if not raw:
        return None

    # Try to find the last complete issue in the issues array
    # by closing off the JSON at a reasonable point
    attempts = [
        raw + '}]}',
        raw + '"}]}',
        raw + '"}]}'  ,
        raw + '"]}}',
    ]

    # Also try truncating to last complete issue
    last_brace = raw.rfind('},')
    if last_brace > 0:
        attempts.insert(0, raw[:last_brace + 1] + ']}')

    for fixed in attempts:
        try:
            result = json.loads(fixed)
            if isinstance(result, dict) and "accessibility_score" in result:
                logger.info("Successfully repaired truncated JSON response")
                if not isinstance(result.get("issues"), list):
                    result["issues"] = []
                return result
        except (json.JSONDecodeError, Exception):
            continue

    return None


def audit_dataset(
    dataset,
    model_name="gemini-2.5-flash",
    max_samples=None,
    delay_between_calls=0.5,
):
    """
    Run accessibility audit on all samples in a FiftyOne dataset.

    Stores results as fields on each sample:
        - accessibility_score (float): 0-100
        - scene_type (str): type of space
        - overall_accessible (bool): wheelchair accessible?
        - issues_json (str): JSON string of issues list
        - issue_count (int): number of issues found
        - issue_types (list[str]): list of issue type strings
        - severity_tags (list[str]): list of severity levels found
        - audit_status (str): "success" or "failed"

    Args:
        dataset: a FiftyOne Dataset
        model_name: Gemini model name
        max_samples: optional cap on samples to process
        delay_between_calls: seconds to wait between API calls (rate limiting)

    Returns:
        dict with audit summary stats
    """
    configure_gemini()

    view = dataset
    if max_samples:
        view = dataset.take(max_samples)

    total = len(view)
    success_count = 0
    fail_count = 0

    logger.info(f"Starting accessibility audit on {total} samples...")

    for i, sample in enumerate(view, 1):
        logger.info(f"Auditing sample {i}/{total}: {sample.filepath}")

        result = audit_single_image(sample.filepath, model_name=model_name)

        if result:
            sample["accessibility_score"] = result.get("accessibility_score")
            sample["scene_type"] = result.get("scene_type", "unknown")
            sample["overall_accessible"] = result.get("overall_accessible", False)
            sample["issues_json"] = json.dumps(result.get("issues", []))
            sample["issue_count"] = len(result.get("issues", []))
            sample["issue_types"] = [
                issue.get("issue_type", "other")
                for issue in result.get("issues", [])
            ]
            sample["severity_tags"] = list(
                set(issue.get("severity", "minor") for issue in result.get("issues", []))
            )
            sample["audit_status"] = "success"

            # Add severity-based tags
            for severity in sample["severity_tags"]:
                sample.tags.append(severity)
            if result.get("overall_accessible"):
                sample.tags.append("accessible")
            else:
                sample.tags.append("inaccessible")

            success_count += 1
        else:
            sample["audit_status"] = "failed"
            fail_count += 1

        sample.save()

        # Rate limiting
        if delay_between_calls > 0 and i < total:
            time.sleep(delay_between_calls)

    logger.info(f"Audit complete: {success_count} success, {fail_count} failed")

    return {
        "total": total,
        "success": success_count,
        "failed": fail_count,
    }
