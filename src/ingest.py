"""
AccessCheck — Dataset Ingestion Helpers

Functions to load datasets from various sources into FiftyOne.
"""

import os
import logging
import importlib.util
from pathlib import Path

import fiftyone as fo

logger = logging.getLogger(__name__)
_VIDEO_SAMPLER_MODULE = None


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

    dataset = fouh.load_from_hub(
        "comarti15/accessibility-rotterdam-the-netherlands",
        name=dataset_name,
        max_samples=max_samples,
        overwrite=True,
    )
    dataset.persistent = True
    dataset.save()

    logger.info(f"Loaded {len(dataset)} samples into dataset '{dataset_name}'")
    return dataset


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
