"""
AccessCheck — FastAPI Backend Server

Bridges the React frontend with the Gemini Vision audit pipeline.
Run with: python server.py
"""

import json
import logging
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

# Add src/ and project root to path for existing module imports
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from audit_agent import audit_single_image, configure_gemini, RateLimitError
from prompts import SEVERITY_WEIGHTS

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AccessCheck API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rotterdam dataset cache ─────────────────────────────────────────────────

_rotterdam_cache = {}  # name -> filepath mapping

# Maps frontend sample names to extracted image files + labels
ROTTERDAM_SAMPLE_MAP = {
    "RTM — 0042": {"file": "sample_1_inaccessible.jpg", "label": "inaccessible"},
    "RTM — 0118": {"file": "sample_2_accessible.jpg",   "label": "accessible"},
    "RTM — 0203": {"file": "sample_3_inaccessible.jpg", "label": "inaccessible"},
    "RTM — 0311": {"file": "sample_4_accessible.jpg",   "label": "accessible"},
    "RTM — 0407": {"file": "sample_5_inaccessible.jpg", "label": "inaccessible"},
    "RTM — 0512": {"file": "sample_6_accessible.jpg",   "label": "accessible"},
}


def _get_rotterdam_images():
    """
    Load Rotterdam Accessibility dataset images.

    First checks for pre-extracted images in .cache/rotterdam/images/.
    If not found, downloads the zip from HuggingFace and extracts samples.
    """
    global _rotterdam_cache
    if _rotterdam_cache:
        return _rotterdam_cache

    images_dir = PROJECT_ROOT / ".cache" / "rotterdam" / "images"

    # Check if images are already extracted
    all_present = images_dir.exists() and all(
        (images_dir / info["file"]).exists() for info in ROTTERDAM_SAMPLE_MAP.values()
    )

    if not all_present:
        logger.info("Rotterdam sample images not found. Downloading from HuggingFace...")
        try:
            _download_rotterdam_samples(images_dir)
        except Exception as e:
            logger.error(f"Failed to download Rotterdam dataset: {e}")
            return {}

    # Build cache from extracted images
    for name, info in ROTTERDAM_SAMPLE_MAP.items():
        img_path = images_dir / info["file"]
        if img_path.exists():
            _rotterdam_cache[name] = str(img_path)
        else:
            logger.warning(f"Missing image for {name}: {img_path}")

    logger.info(f"Rotterdam dataset ready: {len(_rotterdam_cache)} samples")
    return _rotterdam_cache


def _download_rotterdam_samples(images_dir):
    """
    Download Rotterdam dataset zip from HuggingFace and extract
    a representative set of accessible/inaccessible samples.
    """
    import random
    import zipfile
    from huggingface_hub import hf_hub_download

    images_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading Rotterdam dataset from HuggingFace (354 MB)...")
    zip_path = hf_hub_download(
        "comarti15/accessibility-rotterdam-the-netherlands",
        "Data Challenge.zip",
        repo_type="dataset",
    )
    logger.info(f"Downloaded. Extracting samples...")

    with zipfile.ZipFile(zip_path, "r") as zf:
        all_names = zf.namelist()
        accessible = [n for n in all_names if "/Accessible/" in n and n.lower().endswith(".jpg")]
        inaccessible = [n for n in all_names if "/Inaccessible/" in n and n.lower().endswith(".jpg")]

        random.seed(42)
        picks_acc = random.sample(accessible, min(3, len(accessible)))
        picks_inacc = random.sample(inaccessible, min(3, len(inaccessible)))

        # Interleave: inacc, acc, inacc, acc, inacc, acc (matches frontend order)
        ordered = []
        for i in range(3):
            if i < len(picks_inacc):
                ordered.append(picks_inacc[i])
            if i < len(picks_acc):
                ordered.append(picks_acc[i])

        sample_files = list(ROTTERDAM_SAMPLE_MAP.values())
        for i, zip_name in enumerate(ordered):
            if i >= len(sample_files):
                break
            out_path = images_dir / sample_files[i]["file"]
            with zf.open(zip_name) as src, open(out_path, "wb") as dst:
                dst.write(src.read())
            logger.info(f"  Extracted: {sample_files[i]['file']} from {zip_name.split('/')[-1]}")

    logger.info("Rotterdam samples ready.")


# ── Video processing (reuse plugin logic without FiftyOne dependency) ────────

def _download_youtube_video(url, output_dir):
    """Download a YouTube video using yt-dlp."""
    import yt_dlp

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(title)s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = ydl.prepare_filename(info)
        requested_downloads = info.get("requested_downloads") or []
        if requested_downloads:
            maybe_path = requested_downloads[0].get("filepath")
            if maybe_path and os.path.isfile(maybe_path):
                video_path = maybe_path

    if not os.path.isfile(video_path):
        raise RuntimeError(f"yt-dlp completed but no file found at: {video_path}")

    metadata = {
        "title": info.get("title", "Unknown"),
        "duration_sec": info.get("duration", 0) or 0,
    }
    return video_path, metadata


def _extract_frames(video_path, output_dir, max_frames=50, interval_seconds=3.0,
                    scene_threshold=0.3):
    """
    Extract key frames from video using hybrid strategy.
    Simplified version of the video-sampler plugin for API use.
    """
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    if fps <= 0:
        fps = 30.0
    interval_frames = max(1, int(round(interval_seconds * fps)))

    os.makedirs(output_dir, exist_ok=True)

    candidates = []
    prev_frame = None
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        timestamp = frame_idx / fps

        # Hybrid strategy: uniform interval OR scene change
        is_interval = (frame_idx % interval_frames == 0)
        is_scene_change = False
        if prev_frame is None:
            is_scene_change = True
        else:
            # Histogram-based difference
            hist1 = cv2.calcHist([prev_frame], [0, 1, 2], None, [8, 8, 8],
                                 [0, 256, 0, 256, 0, 256])
            hist2 = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8],
                                 [0, 256, 0, 256, 0, 256])
            cv2.normalize(hist1, hist1)
            cv2.normalize(hist2, hist2)
            corr = float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL))
            corr = max(-1.0, min(1.0, corr))
            diff = (1.0 - corr) / 2.0
            is_scene_change = diff > scene_threshold

        if is_interval or is_scene_change:
            candidates.append({
                "frame": frame.copy(),
                "frame_number": frame_idx,
                "timestamp_sec": round(timestamp, 3),
            })

        prev_frame = frame
        frame_idx += 1

    cap.release()

    if not candidates:
        raise RuntimeError("No frames extracted from video.")

    # Perceptual hash deduplication
    try:
        import imagehash
        from PIL import Image as PILImage

        deduped = []
        hashes = []
        for c in candidates:
            pil_img = PILImage.fromarray(cv2.cvtColor(c["frame"], cv2.COLOR_BGR2RGB))
            h = imagehash.phash(pil_img, hash_size=8)
            if not any(abs(h - existing) <= 5 for existing in hashes):
                deduped.append(c)
                hashes.append(h)
        candidates = deduped if deduped else candidates
    except ImportError:
        pass  # Skip dedup if imagehash not available

    # Subsample to max_frames
    if len(candidates) > max_frames:
        indices = np.linspace(0, len(candidates) - 1, max_frames, dtype=int)
        candidates = [candidates[i] for i in indices]

    # Write frames to disk
    frame_paths = []
    for idx, c in enumerate(candidates):
        path = os.path.join(output_dir, f"frame_{idx:04d}.jpg")
        cv2.imwrite(path, c["frame"])
        frame_paths.append(path)

    return frame_paths


# ── Result aggregation ───────────────────────────────────────────────────────

def _aggregate_results(results):
    """
    Aggregate multiple per-frame Gemini audit results into the single
    result object the frontend expects.
    """
    valid = [r for r in results if r is not None]
    if not valid:
        raise ValueError("All frames failed to audit")

    # Average score
    scores = [r.get("accessibility_score", 0) for r in valid]
    overall_score = round(sum(scores) / len(scores)) if scores else 0

    # Most common scene type
    scenes = [r.get("scene_type", "unknown") for r in valid]
    scene_type = Counter(scenes).most_common(1)[0][0] if scenes else "unknown"

    # Overall accessible: true only if majority of frames are
    acc_flags = [r.get("overall_accessible", False) for r in valid]
    overall_accessible = sum(acc_flags) > len(acc_flags) / 2

    # Combine all issues, deduplicate by (issue_type, location)
    all_issues = []
    seen = set()
    for r in valid:
        for issue in r.get("issues", []):
            key = (issue.get("issue_type", ""), issue.get("location_in_image", ""))
            if key not in seen:
                seen.add(key)
                all_issues.append(issue)

    return {
        "overall_score": overall_score,
        "scene_type": scene_type,
        "overall_accessible": overall_accessible,
        "issues": all_issues,
    }


def _format_single_result(result):
    """
    Format a single Gemini audit result to match the frontend's expected shape.
    Maps accessibility_score -> overall_score.
    """
    return {
        "overall_score": result.get("accessibility_score", 0),
        "scene_type": result.get("scene_type", "unknown"),
        "overall_accessible": result.get("overall_accessible", False),
        "issues": result.get("issues", []),
    }


# ── Request models ───────────────────────────────────────────────────────────

class YouTubeRequest(BaseModel):
    url: str


class SampleRequest(BaseModel):
    filename: str


# ── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    try:
        configure_gemini()
        logger.info("Gemini client ready")
    except ValueError as e:
        logger.error(f"Gemini setup failed: {e}")
        logger.error("Set GEMINI_API_KEY in .env file to enable auditing")


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    has_key = bool(
        os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    )
    return {"status": "ok", "gemini_configured": has_key}


@app.post("/api/audit/youtube")
async def audit_youtube(req: YouTubeRequest):
    """
    Audit a YouTube video for ADA accessibility issues.

    Pipeline: download → extract frames → audit each with Gemini → aggregate.
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "URL is required")
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(400, "Must be a YouTube URL")

    tmp_dir = tempfile.mkdtemp(prefix="accesscheck_yt_")
    try:
        # Step 1: Download video
        logger.info(f"Downloading YouTube video: {url}")
        video_path, meta = _download_youtube_video(url, tmp_dir)
        logger.info(f"Downloaded: {meta['title']} ({meta['duration_sec']}s)")

        # Step 2: Extract frames (default cap: 50)
        frames_dir = os.path.join(tmp_dir, "frames")
        logger.info("Extracting frames...")
        frame_paths = _extract_frames(video_path, frames_dir, max_frames=50)
        logger.info(f"Extracted {len(frame_paths)} frames")

        # Step 3: Audit each frame with Gemini
        logger.info("Auditing frames with Gemini Vision...")
        results = []
        last_error = None
        for i, fp in enumerate(frame_paths):
            logger.info(f"  Auditing frame {i + 1}/{len(frame_paths)}: {fp}")
            logger.info(f"    File exists: {os.path.isfile(fp)}, size: {os.path.getsize(fp) if os.path.isfile(fp) else 'N/A'}")
            try:
                result = audit_single_image(fp)
                if result is None:
                    logger.error(f"    Frame {i+1} returned None (Gemini call failed silently)")
                else:
                    logger.info(f"    Frame {i+1} score: {result.get('accessibility_score')}")
                results.append(result)
            except RateLimitError as e:
                logger.warning(f"    Frame {i+1} hit rate limit. Retry after {e.retry_after}s")
                raise HTTPException(
                    429,
                    f"Gemini API rate limit reached. Free tier allows 20 requests/day. "
                    f"Please wait ~{e.retry_after}s or use a paid API key."
                )
            except Exception as e:
                logger.error(f"    Frame {i+1} exception: {e}", exc_info=True)
                last_error = str(e)
                results.append(None)

        # Step 4: Aggregate into single result
        valid_count = sum(1 for r in results if r is not None)
        logger.info(f"Audit done: {valid_count}/{len(results)} frames succeeded")

        if valid_count == 0:
            detail = f"All {len(results)} frames failed to audit."
            if last_error:
                detail += f" Last error: {last_error}"
            raise HTTPException(500, detail)

        aggregated = _aggregate_results(results)
        logger.info(f"Audit complete — score: {aggregated['overall_score']}/100, "
                     f"{len(aggregated['issues'])} issues found")
        return aggregated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YouTube audit failed: {e}")
        raise HTTPException(500, f"Audit failed: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/audit/sample")
async def audit_sample(req: SampleRequest):
    """
    Audit a Rotterdam dataset sample for ADA accessibility issues.

    Loads the sample image from the cached HuggingFace dataset and
    sends it to Gemini for analysis.
    """
    filename = req.filename.strip()
    if not filename:
        raise HTTPException(400, "Filename is required")

    try:
        # Load Rotterdam images (cached after first call)
        cache = _get_rotterdam_images()

        if not cache:
            raise HTTPException(
                503,
                "Rotterdam dataset not available. "
                "Check server logs for download errors."
            )

        image_path = cache.get(filename)
        if not image_path:
            # Try fuzzy match (in case of encoding differences in the dash)
            for name, path in cache.items():
                if filename.replace("—", "-").replace(" ", "") in name.replace("—", "-").replace(" ", ""):
                    image_path = path
                    break

        if not image_path:
            available = list(cache.keys())
            raise HTTPException(
                404,
                f"Sample '{filename}' not found. Available: {available}"
            )

        logger.info(f"Auditing Rotterdam sample: {filename}")
        result = audit_single_image(image_path)

        if result is None:
            raise HTTPException(500, "Gemini audit returned no result — check server logs.")

        formatted = _format_single_result(result)
        logger.info(f"Sample audit complete — score: {formatted['overall_score']}/100")
        return formatted

    except HTTPException:
        raise
    except RateLimitError as e:
        raise HTTPException(
            429,
            f"Gemini API rate limit reached. Free tier allows 20 requests/day. "
            f"Please wait ~{e.retry_after}s or use a paid API key."
        )
    except Exception as e:
        logger.error(f"Sample audit failed: {e}")
        raise HTTPException(500, f"Audit failed: {str(e)}")


# ── Run server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting AccessCheck API server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
