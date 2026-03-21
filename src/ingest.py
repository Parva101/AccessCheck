"""
AccessCheck — Dataset Ingestion Helpers

Functions to load datasets from various sources into FiftyOne.
"""

import os
import logging

import fiftyone as fo

logger = logging.getLogger(__name__)


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

    # Import from our plugin
    from plugins.video_sampler import download_youtube_video, extract_frames

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
