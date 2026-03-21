"""
Video Sampler Plugin for FiftyOne
Smart video-to-dataset converter with scene-change detection and perceptual dedup.
"""

import os
import logging
import tempfile

import cv2
import numpy as np
from PIL import Image

import fiftyone as fo
import fiftyone.operators as foo
import fiftyone.operators.types as types

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def download_youtube_video(url, output_dir):
    """Download a YouTube video using yt-dlp and return the file path."""
    import yt_dlp

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        video_metadata = {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "channel": info.get("channel", "Unknown"),
            "url": url,
        }
    return filename, video_metadata


def compute_frame_difference(frame1, frame2):
    """Compute histogram-based difference between two frames (0-1 scale)."""
    hist1 = cv2.calcHist([frame1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist2 = cv2.calcHist([frame2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    return 1.0 - score  # 0 = identical, 1 = completely different


def compute_phash(frame, hash_size=8):
    """Compute perceptual hash of a frame for deduplication."""
    import imagehash
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return imagehash.phash(pil_image, hash_size=hash_size)


def extract_frames(
    video_path,
    output_dir,
    strategy="hybrid",
    max_frames=100,
    interval_seconds=2.0,
    scene_threshold=0.3,
    dedup=True,
    dedup_threshold=5,
):
    """
    Extract frames from a video file using the specified strategy.

    Args:
        video_path: path to the video file
        output_dir: directory to save extracted frame images
        strategy: "uniform", "scene_change", or "hybrid"
        max_frames: maximum number of frames to extract
        interval_seconds: seconds between frames (uniform strategy)
        scene_threshold: difference threshold for scene change (0-1)
        dedup: whether to remove perceptually similar frames
        dedup_threshold: hamming distance threshold for dedup (lower = stricter)

    Returns:
        list of dicts with keys: filepath, timestamp_sec, frame_number
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    os.makedirs(output_dir, exist_ok=True)

    candidates = []
    prev_frame = None
    frame_idx = 0
    interval_frames = int(interval_seconds * fps) if fps > 0 else 30

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps if fps > 0 else 0
        should_extract = False

        if strategy == "uniform":
            should_extract = (frame_idx % interval_frames == 0)

        elif strategy == "scene_change":
            if prev_frame is not None:
                diff = compute_frame_difference(prev_frame, frame)
                should_extract = (diff > scene_threshold)
            else:
                should_extract = True  # always grab first frame

        elif strategy == "hybrid":
            is_interval = (frame_idx % interval_frames == 0)
            is_scene_change = False
            if prev_frame is not None:
                diff = compute_frame_difference(prev_frame, frame)
                is_scene_change = (diff > scene_threshold)
            else:
                is_scene_change = True
            should_extract = is_interval or is_scene_change

        if should_extract:
            candidates.append({
                "frame": frame.copy(),
                "frame_number": frame_idx,
                "timestamp_sec": round(timestamp, 2),
            })

        prev_frame = frame.copy()
        frame_idx += 1

    cap.release()

    # Perceptual deduplication
    if dedup and len(candidates) > 0:
        deduped = [candidates[0]]
        prev_hash = compute_phash(candidates[0]["frame"])
        for c in candidates[1:]:
            curr_hash = compute_phash(c["frame"])
            if abs(curr_hash - prev_hash) >= dedup_threshold:
                deduped.append(c)
                prev_hash = curr_hash
        candidates = deduped

    # Cap to max_frames (evenly sample if too many)
    if len(candidates) > max_frames:
        indices = np.linspace(0, len(candidates) - 1, max_frames, dtype=int)
        candidates = [candidates[i] for i in indices]

    # Save frames to disk
    results = []
    for i, c in enumerate(candidates):
        filename = f"frame_{i:04d}_{c['frame_number']:06d}.jpg"
        filepath = os.path.join(output_dir, filename)
        cv2.imwrite(filepath, c["frame"])
        results.append({
            "filepath": filepath,
            "timestamp_sec": c["timestamp_sec"],
            "frame_number": c["frame_number"],
        })

    return results, {
        "fps": fps,
        "total_frames": total_frames,
        "duration_sec": round(duration, 2),
        "extracted_count": len(results),
    }


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class SampleFromYouTube(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="sample_from_youtube",
            label="Video Sampler: YouTube → Dataset",
            description=(
                "Download a YouTube video and extract smart frames into a "
                "FiftyOne image dataset using scene-change detection and "
                "perceptual deduplication."
            ),
            dynamic=True,
            icon="/assets/icon.svg",
            execute_as_generator=True,
        )

    def resolve_input(self, ctx):
        inputs = types.Object()

        inputs.str(
            "youtube_url",
            label="YouTube URL",
            description="Full YouTube video URL (e.g. https://youtube.com/watch?v=...)",
            required=True,
        )
        inputs.str(
            "dataset_name",
            label="Dataset Name",
            description="Name for the new FiftyOne dataset",
            required=True,
        )

        strategy_choices = types.RadioGroup()
        strategy_choices.add_choice("uniform", label="Uniform (every N seconds)")
        strategy_choices.add_choice("scene_change", label="Scene Change Detection")
        strategy_choices.add_choice("hybrid", label="Hybrid (uniform + scene change)")
        inputs.enum(
            "strategy",
            strategy_choices.values(),
            default="hybrid",
            label="Sampling Strategy",
            description="How to select frames from the video",
            view=strategy_choices,
        )

        inputs.int(
            "max_frames",
            label="Max Frames",
            description="Maximum number of frames to extract",
            default=100,
        )
        inputs.float(
            "interval_seconds",
            label="Interval (seconds)",
            description="Seconds between frames (for uniform/hybrid)",
            default=2.0,
        )
        inputs.float(
            "scene_threshold",
            label="Scene Change Threshold",
            description="Sensitivity for scene detection (0-1, lower = more sensitive)",
            default=0.3,
        )
        inputs.bool(
            "dedup",
            label="Remove Duplicate Frames",
            description="Use perceptual hashing to remove near-identical frames",
            default=True,
        )

        return types.Property(
            inputs,
            view=types.View(label="Video Sampler: YouTube → Dataset"),
        )

    def execute(self, ctx):
        youtube_url = ctx.params["youtube_url"]
        dataset_name = ctx.params["dataset_name"]
        strategy = ctx.params.get("strategy", "hybrid")
        max_frames = ctx.params.get("max_frames", 100)
        interval_seconds = ctx.params.get("interval_seconds", 2.0)
        scene_threshold = ctx.params.get("scene_threshold", 0.3)
        dedup = ctx.params.get("dedup", True)

        # Step 1: Download video
        yield ctx.trigger("set_progress", {"label": "Downloading YouTube video..."})

        download_dir = tempfile.mkdtemp(prefix="video_sampler_")
        video_path, video_meta = download_youtube_video(youtube_url, download_dir)

        yield ctx.trigger("set_progress", {"label": f"Downloaded: {video_meta['title']}"})

        # Step 2: Extract frames
        yield ctx.trigger("set_progress", {"label": "Extracting frames..."})

        frames_dir = os.path.join(download_dir, "frames")
        frame_results, video_info = extract_frames(
            video_path=video_path,
            output_dir=frames_dir,
            strategy=strategy,
            max_frames=max_frames,
            interval_seconds=interval_seconds,
            scene_threshold=scene_threshold,
            dedup=dedup,
        )

        yield ctx.trigger("set_progress", {
            "label": f"Extracted {len(frame_results)} frames, creating dataset..."
        })

        # Step 3: Create FiftyOne dataset
        samples = []
        for fr in frame_results:
            sample = fo.Sample(filepath=fr["filepath"])
            sample["source_url"] = youtube_url
            sample["source_title"] = video_meta["title"]
            sample["timestamp_sec"] = fr["timestamp_sec"]
            sample["frame_number"] = fr["frame_number"]
            sample["sampling_strategy"] = strategy
            samples.append(sample)

        dataset = fo.Dataset(name=dataset_name, overwrite=True)
        dataset.add_samples(samples)
        dataset.persistent = True

        dataset.info["video_metadata"] = video_meta
        dataset.info["extraction_info"] = video_info
        dataset.save()

        yield ctx.trigger("set_progress", {
            "label": (
                f"Done! Created dataset '{dataset_name}' with "
                f"{len(frame_results)} frames from '{video_meta['title']}'"
            )
        })

    def resolve_output(self, ctx):
        outputs = types.Object()
        outputs.str("message", label="Result")
        return types.Property(outputs, view=types.View(label="Video Sampler Complete"))


class SampleFromVideo(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="sample_from_video",
            label="Video Sampler: Local Video → Dataset",
            description=(
                "Extract smart frames from a local video file into a "
                "FiftyOne image dataset."
            ),
            dynamic=True,
            execute_as_generator=True,
        )

    def resolve_input(self, ctx):
        inputs = types.Object()

        inputs.str(
            "video_path",
            label="Video File Path",
            description="Absolute path to a local video file",
            required=True,
        )
        inputs.str(
            "dataset_name",
            label="Dataset Name",
            description="Name for the new FiftyOne dataset",
            required=True,
        )

        strategy_choices = types.RadioGroup()
        strategy_choices.add_choice("uniform", label="Uniform (every N seconds)")
        strategy_choices.add_choice("scene_change", label="Scene Change Detection")
        strategy_choices.add_choice("hybrid", label="Hybrid (uniform + scene change)")
        inputs.enum(
            "strategy",
            strategy_choices.values(),
            default="hybrid",
            label="Sampling Strategy",
            view=strategy_choices,
        )

        inputs.int("max_frames", label="Max Frames", default=100)
        inputs.float("interval_seconds", label="Interval (seconds)", default=2.0)
        inputs.float("scene_threshold", label="Scene Change Threshold", default=0.3)
        inputs.bool("dedup", label="Remove Duplicate Frames", default=True)

        return types.Property(
            inputs,
            view=types.View(label="Video Sampler: Local Video → Dataset"),
        )

    def execute(self, ctx):
        video_path = ctx.params["video_path"]
        dataset_name = ctx.params["dataset_name"]
        strategy = ctx.params.get("strategy", "hybrid")
        max_frames = ctx.params.get("max_frames", 100)
        interval_seconds = ctx.params.get("interval_seconds", 2.0)
        scene_threshold = ctx.params.get("scene_threshold", 0.3)
        dedup = ctx.params.get("dedup", True)

        if not os.path.isfile(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        yield ctx.trigger("set_progress", {"label": "Extracting frames..."})

        frames_dir = tempfile.mkdtemp(prefix="video_sampler_frames_")
        frame_results, video_info = extract_frames(
            video_path=video_path,
            output_dir=frames_dir,
            strategy=strategy,
            max_frames=max_frames,
            interval_seconds=interval_seconds,
            scene_threshold=scene_threshold,
            dedup=dedup,
        )

        yield ctx.trigger("set_progress", {
            "label": f"Extracted {len(frame_results)} frames, creating dataset..."
        })

        samples = []
        for fr in frame_results:
            sample = fo.Sample(filepath=fr["filepath"])
            sample["source_path"] = video_path
            sample["timestamp_sec"] = fr["timestamp_sec"]
            sample["frame_number"] = fr["frame_number"]
            sample["sampling_strategy"] = strategy
            samples.append(sample)

        dataset = fo.Dataset(name=dataset_name, overwrite=True)
        dataset.add_samples(samples)
        dataset.persistent = True

        dataset.info["extraction_info"] = video_info
        dataset.save()

        yield ctx.trigger("set_progress", {
            "label": f"Done! Created '{dataset_name}' with {len(frame_results)} frames"
        })

    def resolve_output(self, ctx):
        outputs = types.Object()
        outputs.str("message", label="Result")
        return types.Property(outputs, view=types.View(label="Video Sampler Complete"))


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(p):
    p.register(SampleFromYouTube)
    p.register(SampleFromVideo)
