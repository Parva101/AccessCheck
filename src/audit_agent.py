"""
AccessCheck — VLM Audit Agent

Sends images to Gemini Vision for accessibility analysis and
parses structured results back into FiftyOne sample fields.
"""

import json
import logging
import time

import google.generativeai as genai
from PIL import Image

from prompts import ACCESSIBILITY_AUDIT_PROMPT

logger = logging.getLogger(__name__)


def configure_gemini(api_key=None):
    """
    Configure the Gemini API. Reads from GEMINI_API_KEY env var if not provided.
    """
    import os

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "Gemini API key not found. Set GEMINI_API_KEY environment variable "
            "or pass api_key parameter."
        )
    genai.configure(api_key=key)
    logger.info("Gemini API configured")


def audit_single_image(image_path, model_name="gemini-2.5-flash"):
    """
    Send a single image to Gemini for accessibility audit.

    Args:
        image_path: path to the image file
        model_name: Gemini model to use

    Returns:
        dict with parsed audit results, or None on failure
    """
    try:
        model = genai.GenerativeModel(model_name)
        image = Image.open(image_path)

        response = model.generate_content(
            [ACCESSIBILITY_AUDIT_PROMPT, image],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )

        # Parse JSON from response
        text = response.text.strip()

        # Handle markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON for {image_path}: {e}")
        logger.debug(f"Raw response: {text}")
        return None
    except Exception as e:
        logger.warning(f"Error auditing {image_path}: {e}")
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
            sample["severity_tags"] = list(set(
                issue.get("severity", "minor")
                for issue in result.get("issues", [])
            ))
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
