# AccessCheck: AI-Powered Accessibility Auditor

## Hackathon: Agents World Visual AI Hackathon at ASU — March 21, 2026

---

## Project Summary

**AccessCheck** is a Visual AI platform that audits buildings, sidewalks, and properties for ADA accessibility compliance. It takes YouTube property tour videos OR street-level images, analyzes them with an AI agent, and produces a scored accessibility report with specific issues, severity ratings, and remediation suggestions — all built on FiftyOne.

**One-liner for judges:** *"Paste a YouTube property tour → get an instant ADA accessibility audit with severity scores and fix recommendations."*

---

## Why This Wins

- **Zero competition** in the FiftyOne ecosystem — no accessibility plugin or workflow exists
- **Real social impact** — 61M Americans with disabilities, ADA compliance is legally required
- **Novel plugin** (video-sampler) that other developers would actually install and use
- **Dramatic demo** — YouTube URL → full audit in minutes
- **Uses FiftyOne deeply** — not just a VLM wrapper

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│                                                                 │
│  1. Rotterdam Accessibility Dataset (1,883 labeled images)      │
│  2. YouTube property tour videos (via video-sampler plugin)     │
│  3. Sidewalk Semantic dataset (1,000+ segmented images)         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              NEW PLUGIN: @yourteam/video-sampler                │
│                                                                 │
│  - Downloads YouTube videos                                     │
│  - Smart frame extraction (scene-change detection)              │
│  - Perceptual deduplication of near-identical frames            │
│  - Configurable: uniform / scene-change / keyframe / hybrid     │
│  - Stores source URL + timestamp on each sample                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FiftyOne Dataset                              │
│                                                                 │
│  Each sample has:                                               │
│  - filepath (image)                                             │
│  - source_url (YouTube URL or dataset origin)                   │
│  - timestamp (seconds into video, if from video)                │
│  - frame_number (if from video)                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│         EXISTING PLUGIN: @AdonaiVera/gemini-vision-plugin       │
│                                                                 │
│  Each image sent to Gemini with accessibility audit prompt       │
│  Returns structured JSON per image:                             │
│  - issues: [{type, severity, description, ada_code, fix}]      │
│  - overall_score: 0-100                                         │
│  - scene_type: "entrance" / "bathroom" / "hallway" / etc.      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│             EXISTING PLUGIN: @voxel51/brain                     │
│                                                                 │
│  - Compute CLIP embeddings on all samples                       │
│  - Cluster similar accessibility issues together                │
│  - Visualization: embedding plot shows issue groupings          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           EXISTING PLUGIN: @voxel51/evaluation                  │
│                                                                 │
│  On Rotterdam dataset: compare our predictions vs ground truth  │
│  Metrics: accuracy, precision, recall                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              SCORING & REPORTING (demo.py)                      │
│                                                                 │
│  - Aggregate all issues across dataset                          │
│  - Compute weighted accessibility score (0-100)                 │
│  - Rank issues by severity                                      │
│  - Generate summary: top issues, worst locations, fix priority  │
│  - Display in FiftyOne App                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
visual-ai-hackathon/
├── README.md                          # Project overview for GitHub submission
├── ACCESS_CHECK_PROJECT.md            # This document
│
├── plugins/
│   └── video-sampler/                 # NEW PLUGIN (the bonus prize plugin)
│       ├── fiftyone.yml               # Plugin config: name, operators list
│       ├── __init__.py                # Operators: sample_from_youtube, sample_from_video
│       └── requirements.txt           # yt-dlp, opencv-python, imagehash
│
├── src/
│   ├── demo.py                        # Main demo script (orchestrates everything)
│   ├── prompts.py                     # Accessibility audit prompt engineering
│   ├── scoring.py                     # Aggregation, scoring, report generation
│   └── ingest.py                      # Dataset loading helpers (Rotterdam, HF, YouTube)
│
└── assets/                            # Screenshots, demo GIFs for README
```

---

## Component Details

### 1. NEW PLUGIN: `video-sampler`

**Location:** `plugins/video-sampler/`

**Why it's novel:** No FiftyOne plugin exposes YouTube download + smart frame extraction as an operator in the App. `fiftyone.utils.youtube` exists in the SDK but requires writing Python code — no UI, no smart sampling.

#### `fiftyone.yml`
```yaml
name: "@yourteam/video-sampler"
version: 1.0.0
description: >
  Smart video-to-dataset converter. Downloads YouTube videos or loads local
  video files and extracts frames using intelligent sampling strategies
  (scene-change detection, perceptual deduplication, uniform interval,
  or hybrid). Creates a FiftyOne image dataset with source metadata.
fiftyone:
  version: "*"
operators:
  - sample_from_youtube
  - sample_from_video
```

#### Operator: `sample_from_youtube`
- **Input form:**
  - `youtube_url` (string, required) — the YouTube video URL
  - `dataset_name` (string, required) — name for the new FiftyOne dataset
  - `sampling_strategy` (enum: "uniform", "scene_change", "hybrid") — how to pick frames
  - `max_frames` (int, default 100) — cap on number of frames to extract
  - `interval_seconds` (float, default 2.0) — for uniform strategy, seconds between frames
  - `scene_threshold` (float, default 30.0) — for scene-change strategy, pixel diff threshold
  - `dedup` (bool, default True) — remove perceptually similar frames
- **Execute logic:**
  1. Download video using `yt_dlp` (FiftyOne already has this as a lazy import)
  2. Open video with OpenCV
  3. Extract frames based on selected strategy:
     - **Uniform:** every N seconds
     - **Scene-change:** compute frame-to-frame histogram difference, extract when diff > threshold
     - **Hybrid:** uniform baseline + bonus frames at scene changes
  4. If dedup=True: compute perceptual hashes (pHash via `imagehash`), drop frames with hamming distance < 5
  5. Save frames as images to disk
  6. Create FiftyOne dataset with fields: `filepath`, `source_url`, `timestamp_sec`, `frame_number`
  7. Return dataset name and frame count
- **Output:** "Created dataset '{name}' with {N} frames from {url}"

#### Operator: `sample_from_video`
- Same as above but takes a local video file path instead of YouTube URL
- Simpler — no download step

#### Key implementation details:
- Use `cv2.VideoCapture` for frame extraction
- Use `cv2.calcHist` + `cv2.compareHist` for scene-change detection
- Use `imagehash.phash` for perceptual deduplication
- Store `yt_dlp` video metadata (title, duration, channel) as dataset info
- Show progress via `execute_as_generator=True` pattern

#### Dependencies (`requirements.txt`):
```
yt-dlp
opencv-python
imagehash
Pillow
```

---

### 2. EXISTING PLUGIN: `@AdonaiVera/gemini-vision-plugin`

**Install:** `fiftyone plugins download https://github.com/AdonaiVera/gemini-vision-plugin`

**What it does:** Sends images to Google Gemini Vision API with a text prompt, returns text response.

**How we use it:** We call Gemini with our custom accessibility audit prompt (see prompts.py below). The raw text response is then parsed into structured FiftyOne fields.

**Required:** `GEMINI_API_KEY` environment variable.

---

### 3. EXISTING PLUGIN: `@voxel51/brain`

**Already included with FiftyOne.**

**How we use it:**
```python
import fiftyone.brain as fob

# Compute embeddings for clustering/visualization
fob.compute_similarity(dataset, brain_key="accessibility_sim", model="clip-vit-base32-torch")

# Visualize in 2D
results = fob.compute_visualization(dataset, brain_key="accessibility_viz", model="clip-vit-base32-torch")
```

This creates an interactive embedding plot in the FiftyOne App where similar accessibility issues cluster together.

---

### 4. EXISTING PLUGIN: `@voxel51/evaluation`

**Already included with FiftyOne.**

**How we use it:** The Rotterdam dataset has binary labels (accessible/inaccessible). After our agent tags each sample, we evaluate:
```python
results = dataset.evaluate_classifications(
    "predicted_accessible",
    gt_field="ground_truth_label",
    eval_key="accessibility_eval"
)
results.print_report()
```

---

### 5. Prompt Engineering (`src/prompts.py`)

This is the "secret sauce" — the prompt that makes Gemini return structured, useful accessibility assessments.

```python
ACCESSIBILITY_AUDIT_PROMPT = """
You are an ADA (Americans with Disabilities Act) accessibility compliance expert.
Analyze this image and identify ALL accessibility barriers or concerns.

For each issue found, provide:
1. issue_type: one of [missing_ramp, narrow_doorway, stairs_only_access, no_grab_bars,
   blocked_pathway, no_curb_cut, high_counter, poor_lighting, no_tactile_paving,
   steep_slope, no_elevator_access, inaccessible_parking, obstructed_sidewalk,
   no_handrail, heavy_door, no_accessible_signage, uneven_surface, other]
2. severity: one of [critical, major, minor]
   - critical: completely prevents access for wheelchair/mobility device users
   - major: significantly hinders access or safety
   - minor: inconvenient but not blocking
3. description: brief description of the specific issue
4. location_in_image: where in the image (e.g., "center", "left entrance", "bathroom doorway")
5. remediation: specific fix recommendation
6. ada_reference: relevant ADA standard (e.g., "ADA 404.2.4 - Door Width")

Also provide:
- scene_type: what kind of space this is (entrance, hallway, bathroom, kitchen,
  sidewalk, parking, stairway, bedroom, outdoor_path, other)
- overall_accessible: true/false — is this space accessible to wheelchair users?
- accessibility_score: 0-100 (100 = fully accessible)

Respond ONLY in valid JSON format:
{
  "scene_type": "...",
  "overall_accessible": true/false,
  "accessibility_score": 0-100,
  "issues": [
    {
      "issue_type": "...",
      "severity": "...",
      "description": "...",
      "location_in_image": "...",
      "remediation": "...",
      "ada_reference": "..."
    }
  ]
}

If the image shows a fully accessible space with no issues, return an empty issues
array and accessibility_score of 100. If the image is not of a building/space
(e.g., sky, nature, abstract), set scene_type to "not_applicable" and score to null.
"""
```

---

### 6. Scoring & Report (`src/scoring.py`)

After the VLM tags every sample, aggregate into a property-level report:

```python
def compute_accessibility_report(dataset):
    """
    Aggregates per-sample accessibility findings into an overall report.

    Returns dict with:
    - overall_score: weighted average of all sample scores (0-100)
    - total_issues: count of all issues found
    - critical_count, major_count, minor_count: by severity
    - issues_by_type: {issue_type: count} — e.g., {"missing_ramp": 5, "narrow_doorway": 3}
    - issues_by_scene: {scene_type: count} — e.g., {"bathroom": 4, "entrance": 6}
    - top_5_worst: the 5 samples with lowest accessibility scores
    - remediation_priority: ordered list of fixes ranked by severity * frequency
    """
```

---

### 7. Main Demo Script (`src/demo.py`)

This is the orchestration script that runs the full pipeline:

```python
"""
AccessCheck Demo — Full Pipeline

Usage:
    python demo.py                         # Run on Rotterdam dataset
    python demo.py --youtube URL           # Run on YouTube property tour
    python demo.py --images /path/to/dir   # Run on local images
"""

# STEP 1: Load dataset
# - Rotterdam: fouh.load_from_hub("comarti15/accessibility-rotterdam-the-netherlands")
# - YouTube: use video-sampler plugin to extract frames
# - Images: fo.Dataset.from_images_dir(path)

# STEP 2: Run accessibility audit
# - Loop through samples (or use delegated execution)
# - Send each image to Gemini with ACCESSIBILITY_AUDIT_PROMPT
# - Parse JSON response
# - Store structured fields on each sample:
#   sample["accessibility_score"] = response["accessibility_score"]
#   sample["scene_type"] = response["scene_type"]
#   sample["overall_accessible"] = response["overall_accessible"]
#   sample["issues"] = response["issues"]  # stored as JSON string or FiftyOne labels
#   sample["severity_tags"] = [issue["severity"] for issue in response["issues"]]
#   sample["issue_types"] = [issue["issue_type"] for issue in response["issues"]]

# STEP 3: Compute Brain embeddings
# - fob.compute_similarity(dataset, ...)
# - fob.compute_visualization(dataset, ...)

# STEP 4: Evaluate (on Rotterdam dataset)
# - Compare our predictions against ground truth labels
# - Print accuracy, precision, recall

# STEP 5: Generate report
# - Call compute_accessibility_report(dataset)
# - Print summary to console
# - Store on dataset.info for display in App

# STEP 6: Launch FiftyOne App
# - session = fo.launch_app(dataset)
# - User can browse, filter by severity, view embedding clusters
```

---

## Datasets

### Primary: Rotterdam Accessibility (MUST USE)
```python
import fiftyone.utils.huggingface as fouh
dataset = fouh.load_from_hub("comarti15/accessibility-rotterdam-the-netherlands")
```
- 1,883 street-level photos from Rotterdam, Netherlands
- Binary labels: accessible vs inaccessible
- Sourced from Google Street View
- Labeled for: blocked sidewalks, missing ramps, obstacles, improperly parked scooters
- Apache 2.0 license
- **Use this for validation and the main demo**

### Secondary: YouTube Property Tours (THE WOW FACTOR)
```python
# Using our video-sampler plugin:
# Operator: sample_from_youtube
# Input: any YouTube property tour URL
# Search YouTube for: "ADA accessible home tour" or "wheelchair accessible house tour"
# Or any standard property tour to show what's NOT accessible
```
- Dynamic — download during the demo
- Shows interior accessibility (doorways, bathrooms, kitchens, stairs)
- **Use this for the "wow" moment in the presentation**

### Optional: Sidewalk Semantic
```python
dataset = fouh.load_from_hub("segments/sidewalk-semantic")
```
- 1,000+ sidewalk images with 35 semantic segmentation classes
- Classes include: curb, stairs, door, wall, fence — all relevant
- Requires accepting terms on HuggingFace (may be slow during hackathon)
- **Only use if you have time — not essential**

---

## How FiftyOne Is Used (judges will look for this)

| Feature | Where We Use It |
|---|---|
| **Dataset creation** | Loading from HuggingFace, creating from video frames |
| **Custom sample fields** | `accessibility_score`, `scene_type`, `issues`, `severity_tags`, `issue_types` |
| **Tags** | Tag samples as "critical", "major", "minor", "accessible" |
| **Filtering/Views** | `dataset.match(F("accessibility_score") < 50)` — show only low-scoring |
| **Brain embeddings** | CLIP embeddings → similarity search → visualization plot |
| **Evaluation** | Classification evaluation on Rotterdam ground truth |
| **App browsing** | Visual inspection of results, click through issues |
| **Plugin system** | Our custom video-sampler plugin with operators |
| **Operators** | Custom operators with input forms, progress, output display |

---

## Task Division (2 people, ~4 hours)

### Person A: Plugin + Data Pipeline
| Time | Task |
|---|---|
| 10:30-11:30 | Set up environment: `pip install fiftyone`, download existing plugins, get Gemini API key |
| 11:30-1:00 | Build `video-sampler` plugin: `fiftyone.yml` + `__init__.py` with both operators. Test with a YouTube video |
| 1:00-1:30 | Lunch + watch Gemini talk |
| 1:30-2:30 | Write `ingest.py` — load Rotterdam dataset, test YouTube pipeline end-to-end |
| 2:30-3:30 | Integrate: make sure video-sampler output feeds smoothly into the audit pipeline |
| 3:30-4:00 | Help Person B with demo polish, write plugin README |
| 4:00-5:00 | Presentation slides (4-6 slides), final testing, push to GitHub |

### Person B: AI Agent + Scoring + Demo
| Time | Task |
|---|---|
| 10:30-11:30 | Set up environment: `pip install fiftyone`, set up Gemini API key, test basic Gemini call |
| 11:30-1:00 | Write `prompts.py` — craft and test the accessibility audit prompt. Iterate until Gemini returns good structured JSON |
| 1:00-1:30 | Lunch + watch Gemini talk |
| 1:30-2:30 | Write `demo.py` — the main orchestration script. Get it working on Rotterdam dataset |
| 2:30-3:30 | Write `scoring.py` — aggregation, scoring, report. Add Brain embeddings + evaluation |
| 3:30-4:00 | Polish demo flow, handle edge cases (VLM returns bad JSON, etc.) |
| 4:00-5:00 | Presentation slides (4-6 slides), rehearse demo, push to GitHub |

---

## Setup Instructions

### 1. Install FiftyOne
```bash
pip install fiftyone
```

### 2. Install existing plugins
```bash
fiftyone plugins download https://github.com/AdonaiVera/gemini-vision-plugin
```

### 3. Set API key
```bash
# Windows PowerShell
$env:GEMINI_API_KEY = "your-key-here"

# Or get a free key at https://aistudio.google.com/apikey
```

### 4. Install video-sampler dependencies
```bash
pip install yt-dlp opencv-python imagehash Pillow
```

### 5. Install our plugin locally
```bash
# From the project root, symlink the plugin:
# On Windows (PowerShell as admin):
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.fiftyone\plugins\video-sampler" -Target ".\plugins\video-sampler"

# Or copy it:
Copy-Item -Recurse .\plugins\video-sampler "$env:USERPROFILE\.fiftyone\plugins\video-sampler"
```

### 6. Test it works
```python
import fiftyone as fo
import fiftyone.utils.huggingface as fouh

# Load Rotterdam dataset
dataset = fouh.load_from_hub("comarti15/accessibility-rotterdam-the-netherlands")
session = fo.launch_app(dataset)
```

---

## Demo Presentation Outline (5 min, 4-6 slides)

### Slide 1: The Problem
- 61M Americans have disabilities
- ADA compliance is legally required but auditing is manual, expensive, slow
- Property buyers/renters with disabilities can't easily assess accessibility from listings

### Slide 2: Our Solution — AccessCheck
- AI agent that audits any building/property for accessibility barriers
- Works on street photos, property tour videos, any image source
- Produces scored reports with specific issues and fix recommendations
- Built on FiftyOne with a reusable video-sampler plugin

### Slide 3: Live Demo — Rotterdam Dataset
- Show FiftyOne App with audited Rotterdam images
- Filter to critical issues → show real blocked sidewalks, missing ramps
- Show embedding visualization with clustered issue types

### Slide 4: Live Demo — YouTube Property Tour
- Paste a YouTube URL → video-sampler extracts frames
- Agent audits interior rooms → show narrow doorways, stairs, no grab bars
- Show the accessibility score and report

### Slide 5: Technical Architecture
- Show the architecture diagram
- Highlight: novel video-sampler plugin + existing FiftyOne plugins + Gemini Vision
- Show evaluation metrics on Rotterdam dataset

### Slide 6: Impact & What's Next
- Could be used by: city planners, real estate platforms, disability advocates, building inspectors
- The video-sampler plugin is general-purpose — useful for ANY video analysis
- Future: integrate with Google Street View API for city-wide audits

---

## Prize Targets

| Prize | Our Angle |
|---|---|
| **Grand Prize** | Complete working system: novel plugin + real data + YouTube + scoring |
| **Most Impactful** | Directly helps people with disabilities, addresses legal compliance |
| **Most Innovative** | First accessibility AI in FiftyOne, novel video-sampler plugin |
| **Bonus: Build Your Own Plugin** | `video-sampler` is a legitimate reusable plugin |

---

## Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Gemini API rate limits | Use `max_samples` to limit to 50-100 for demo; batch with delays |
| Gemini returns non-JSON | Wrap in try/catch, retry with "respond ONLY in JSON" reinforcement |
| YouTube download fails | Have a pre-downloaded backup video ready |
| Rotterdam dataset too large | Use `max_samples=200` when loading from HF for faster demo |
| No internet at venue | Pre-cache everything: dataset, video frames, VLM results |
| Plugin installation issues | Test symlink/copy method before demo; have manual fallback |

---

## Quick Reference: FiftyOne API Cheat Sheet

```python
import fiftyone as fo
import fiftyone.zoo as foz
import fiftyone.brain as fob
import fiftyone.utils.huggingface as fouh
from fiftyone import ViewField as F

# Load dataset from HuggingFace
dataset = fouh.load_from_hub("comarti15/accessibility-rotterdam-the-netherlands")

# Load from images directory
dataset = fo.Dataset.from_images_dir("/path/to/images", name="my-dataset")

# Add fields to a sample
sample["accessibility_score"] = 72
sample["scene_type"] = "entrance"
sample["issues_json"] = '...'
sample.tags.append("critical")
sample.save()

# Filter dataset
critical_view = dataset.match(F("accessibility_score") < 30)
entrance_view = dataset.match(F("scene_type") == "entrance")
tagged_view = dataset.match_tags("critical")

# Brain embeddings
fob.compute_similarity(dataset, brain_key="sim", model="clip-vit-base32-torch")
fob.compute_visualization(dataset, brain_key="viz", model="clip-vit-base32-torch")

# Evaluation
results = dataset.evaluate_classifications("pred_field", gt_field="gt_field", eval_key="eval")
results.print_report()

# Launch app
session = fo.launch_app(dataset)
```

---

## IMPORTANT NOTES

1. **The novel plugin is `video-sampler`** — this is what qualifies us for the bonus prize. It must be a proper FiftyOne plugin with `fiftyone.yml` and registered operators.

2. **We do NOT build the accessibility logic as a plugin** — it's a vertical application (demo script), not a reusable developer tool. The plugin we build is the general-purpose video-sampler.

3. **Use Gemini Vision via the existing plugin OR direct API calls** — either works. The existing plugin may be easier for App-based demo; direct API calls give more control for the script.

4. **Pre-cache results** — run the full pipeline once before the demo so everything is loaded. During the live demo, show pre-computed results but also show a live YouTube ingest to prove it works.

5. **GitHub repo must be pushed by 5 PM** — include README, code, plugin, and demo instructions.
