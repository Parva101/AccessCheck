"""
AccessCheck — Dataset Ingestion Helpers

Functions to load datasets from various sources into FiftyOne.
"""

import os
import logging
import importlib.util
import random
import zipfile
from pathlib import Path

import fiftyone as fo

logger = logging.getLogger(__name__)
_VIDEO_SAMPLER_MODULE = None
_ROTTERDAM_REPO_ID = "comarti15/accessibility-rotterdam-the-netherlands"
_ROTTERDAM_ZIP_NAME = "Data Challenge.zip"


def _load_rotterdam_from_zip(max_samples=None, dataset_name="rotterdam-accessibility"):
    """
    Fallback loader for the Rotterdam dataset when FiftyOne metadata is unavailable
    on HuggingFace Hub.

    Downloads the dataset zip, extracts a deterministic sample of images, and
    builds a FiftyOne dataset with a `gt_accessibility` label field.
    """
    from huggingface_hub import hf_hub_download

    logger.info("Falling back to zip-based Rotterdam loader...")
    zip_path = hf_hub_download(
        _ROTTERDAM_REPO_ID,
        _ROTTERDAM_ZIP_NAME,
        repo_type="dataset",
    )

    cache_root = Path(__file__).resolve().parent.parent / ".cache" / "rotterdam" / "full_images"
    cache_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        accessible = [
            m for m in members
            if "/Accessible/" in m and m.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        inaccessible = [
            m for m in members
            if "/Inaccessible/" in m and m.lower().endswith((".jpg", ".jpeg", ".png"))
        ]

        total = len(accessible) + len(inaccessible)
        if total == 0:
            raise RuntimeError("No image files found in Rotterdam dataset zip")

        if max_samples is None or max_samples >= total:
            chosen = accessible + inaccessible
        else:
            rng = random.Random(42)
            target_inacc = max(1, round(max_samples * len(inaccessible) / total))
            target_inacc = min(target_inacc, len(inaccessible))
            target_acc = max_samples - target_inacc
            target_acc = min(target_acc, len(accessible))
            if target_acc + target_inacc < max_samples:
                remaining = max_samples - (target_acc + target_inacc)
                add_acc = min(remaining, len(accessible) - target_acc)
                target_acc += add_acc
                remaining -= add_acc
                if remaining > 0:
                    target_inacc += min(remaining, len(inaccessible) - target_inacc)

            chosen = (
                rng.sample(accessible, target_acc)
                + rng.sample(inaccessible, target_inacc)
            )
            rng.shuffle(chosen)

        records = []
        for member in chosen:
            parts = member.split("/")
            split = parts[1] if len(parts) > 2 else "unknown"
            label_raw = parts[2] if len(parts) > 3 else "unknown"
            label = "accessible" if label_raw.lower() == "accessible" else "inaccessible"
            filename = Path(member).name

            out_dir = cache_root / split / label
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / filename

            if not out_path.exists():
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())

            records.append(
                {
                    "filepath": str(out_path),
                    "gt_label": label,
                    "split": split.lower(),
                    "source_member": member,
                }
            )

    dataset = fo.Dataset(name=dataset_name, overwrite=True)
    samples = []
    for rec in records:
        sample = fo.Sample(filepath=rec["filepath"])
        sample["gt_accessibility"] = fo.Classification(label=rec["gt_label"])
        sample["source_split"] = rec["split"]
        sample["source_member"] = rec["source_member"]
        samples.append(sample)

    dataset.add_samples(samples)
    dataset.persistent = True
    dataset.info["source"] = _ROTTERDAM_REPO_ID
    dataset.info["loader"] = "zip-fallback"
    dataset.save()

    logger.info(f"Loaded {len(dataset)} samples into dataset '{dataset_name}' (zip fallback)")
    return dataset


def _load_video_sampler_module():
    """
    Dynamically load the local `plugins/video-sampler/__init__.py` module.

    The plugin folder uses a hyphen, so it cannot be imported via a normal
    dotted Python package path.
    """
    global _VIDEO_SAMPLER_MODULE

    if _VIDEO_SAMPLER_MODULE is not None:
        return _VIDEO_SAMPLER_MODULE

    plugin_init = (
        Path(__file__).resolve().parent.parent
        / "plugins"
        / "video-sampler"
        / "__init__.py"
    )
    if not plugin_init.is_file():
        raise FileNotFoundError(
            f"Could not locate video-sampler plugin module at: {plugin_init}"
        )

    spec = importlib.util.spec_from_file_location(
        "accesscheck_video_sampler", str(plugin_init)
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Failed to create import spec for video-sampler module: {plugin_init}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _VIDEO_SAMPLER_MODULE = module
    return module


def load_rotterdam_dataset(max_samples=None, dataset_name="rotterdam-accessibility"):
    """
    Load the Rotterdam Accessibility dataset from HuggingFace.

    This dataset contains 1,883 street-level photos labeled as
    accessible or inaccessible for mobility-impaired users.

    Args:
        max_samples: optional cap on number of samples to load
        dataset_name: name for the FiftyOne dataset

    Returns:
        a FiftyOne Dataset
    """
    import fiftyone.utils.huggingface as fouh

    logger.info("Loading Rotterdam Accessibility dataset from HuggingFace...")
    try:
        dataset = fouh.load_from_hub(
            _ROTTERDAM_REPO_ID,
            name=dataset_name,
            max_samples=max_samples,
            overwrite=True,
        )
        dataset.persistent = True
        dataset.save()
        logger.info(f"Loaded {len(dataset)} samples into dataset '{dataset_name}'")
        return dataset
    except ValueError as e:
        if "Could not find fiftyone metadata" not in str(e):
            raise
        logger.warning(
            "HuggingFace repo has no FiftyOne metadata. "
            "Using zip-based fallback loader."
        )
        return _load_rotterdam_from_zip(
            max_samples=max_samples,
            dataset_name=dataset_name,
        )


def load_from_images_dir(images_dir, dataset_name="local-images"):
    """
    Load images from a local directory into a FiftyOne dataset.

    Args:
        images_dir: path to a directory of images
        dataset_name: name for the FiftyOne dataset

    Returns:
        a FiftyOne Dataset
    """
    if not os.path.isdir(images_dir):
        raise ValueError(f"Directory not found: {images_dir}")

    dataset = fo.Dataset.from_images_dir(
        images_dir,
        name=dataset_name,
    )
    dataset.persistent = True
    dataset.save()

    logger.info(f"Loaded {len(dataset)} images from '{images_dir}'")
    return dataset


def load_from_youtube(youtube_url, dataset_name="youtube-property-tour", **kwargs):
    """
    Download a YouTube video, extract frames, and create a FiftyOne dataset.

    This uses our video-sampler plugin's core extraction logic directly.

    Args:
        youtube_url: YouTube video URL
        dataset_name: name for the FiftyOne dataset
        **kwargs: passed to extract_frames() — strategy, max_frames,
                  interval_seconds, scene_threshold, dedup

    Returns:
        a FiftyOne Dataset
    """
    import tempfile

    video_sampler = _load_video_sampler_module()
    download_youtube_video = getattr(video_sampler, "download_youtube_video", None)
    extract_frames = getattr(video_sampler, "extract_frames", None)
    if download_youtube_video is None or extract_frames is None:
        raise ImportError(
            "video-sampler plugin module is missing `download_youtube_video` "
            "and/or `extract_frames` functions"
        )

    download_dir = tempfile.mkdtemp(prefix="accesscheck_")

    logger.info(f"Downloading video from {youtube_url}...")
    video_path, video_meta = download_youtube_video(youtube_url, download_dir)
    logger.info(f"Downloaded: {video_meta['title']}")

    frames_dir = os.path.join(download_dir, "frames")
    logger.info("Extracting frames...")
    frame_results, video_info = extract_frames(
        video_path=video_path,
        output_dir=frames_dir,
        **kwargs,
    )
    logger.info(f"Extracted {len(frame_results)} frames")

    samples = []
    for fr in frame_results:
        sample = fo.Sample(filepath=fr["filepath"])
        sample["source_url"] = youtube_url
        sample["source_title"] = video_meta["title"]
        sample["timestamp_sec"] = fr["timestamp_sec"]
        sample["frame_number"] = fr["frame_number"]
        samples.append(sample)

    dataset = fo.Dataset(name=dataset_name, overwrite=True)
    dataset.add_samples(samples)
    dataset.persistent = True
    dataset.info["video_metadata"] = video_meta
    dataset.info["extraction_info"] = video_info
    dataset.save()

    logger.info(f"Created dataset '{dataset_name}' with {len(dataset)} samples")
    return dataset
