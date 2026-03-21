# ♿ AccessCheck — AI-Powered Accessibility Auditor

> Paste a YouTube property tour → get an instant ADA accessibility audit with severity scores and fix recommendations — all powered by FiftyOne.

Built for the [Agents World: Visual AI Hackathon at ASU](https://voxel51.com/events/agents-world-visual-ai-hackathon-at-asu-march-21-2026) — March 21, 2026.

---

## What It Does

AccessCheck is a Visual AI platform that audits buildings, sidewalks, and properties for **ADA accessibility compliance**. It takes YouTube property tour videos OR street-level images, analyzes them with an AI agent powered by Gemini Vision, and produces a scored accessibility report with specific issues, severity ratings, and remediation suggestions.

### Features

- 🎬 **YouTube → Dataset** — Paste any property tour URL, smart frame extraction with scene-change detection and perceptual dedup
- 🤖 **AI Accessibility Agent** — Gemini Vision analyzes each image for ADA barriers (missing ramps, narrow doorways, no grab bars, blocked paths, etc.)
- 📊 **Structured Scoring** — Every image gets an accessibility score (0-100), issue categories, severity ratings, and specific fix recommendations
- 🧠 **Embedding Clustering** — FiftyOne Brain groups similar accessibility issues together for pattern discovery
- 📋 **Automated Report** — Aggregated property-level score with prioritized remediation plan

---

## Architecture

```
YouTube URL / Images / HuggingFace Dataset
        │
        ▼
┌──────────────────────────┐
│  video-sampler plugin    │  ← NEW plugin (bonus prize)
│  Smart frame extraction  │
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  Gemini Vision VLM       │  ← Accessibility audit prompt
│  (gemini-vision-plugin)  │
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  FiftyOne Brain          │  ← CLIP embeddings + clustering
│  (@voxel51/brain)        │
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│  Scoring + Report        │  ← Aggregation, priority ranking
└──────────────────────────┘
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Install FiftyOne plugins
```bash
fiftyone plugins download https://github.com/AdonaiVera/gemini-vision-plugin
```

### 3. Install our video-sampler plugin
```bash
# Windows PowerShell
Copy-Item -Recurse .\plugins\video-sampler "$env:USERPROFILE\.fiftyone\plugins\video-sampler"

# macOS/Linux
cp -r ./plugins/video-sampler ~/.fiftyone/plugins/video-sampler
```

### 4. Set your Gemini API key
```bash
# Get a free key at https://aistudio.google.com/apikey

# Windows PowerShell
$env:GEMINI_API_KEY = "your-key-here"

# macOS/Linux
export GEMINI_API_KEY="your-key-here"
```

### 5. Run the demo
```bash
cd src

# Default: Rotterdam accessibility dataset (50 samples for quick demo)
python demo.py --rotterdam --max-samples 50

# From a YouTube property tour
python demo.py --youtube "https://www.youtube.com/watch?v=VIDEO_ID"

# From local images
python demo.py --images /path/to/images
```

---

## Project Structure

```
AccessCheck/
├── README.md                    # This file
├── ACCESS_CHECK_PROJECT.md      # Detailed project spec
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
├── .gitignore
│
├── plugins/
│   └── video-sampler/           # NEW FiftyOne plugin
│       ├── fiftyone.yml         # Plugin config
│       ├── __init__.py          # Operators: sample_from_youtube, sample_from_video
│       └── requirements.txt     # Plugin dependencies
│
└── src/
    ├── demo.py                  # Main orchestration script
    ├── audit_agent.py           # VLM audit logic (Gemini calls + parsing)
    ├── prompts.py               # Accessibility audit prompt templates
    ├── scoring.py               # Aggregation, scoring, report generation
    └── ingest.py                # Dataset loading helpers
```

---

## Datasets

| Dataset | Source | Size | Use |
|---|---|---|---|
| Rotterdam Accessibility | [HuggingFace](https://huggingface.co/datasets/comarti15/accessibility-rotterdam-the-netherlands) | 1,883 images | Primary demo — pre-labeled street-level photos |
| YouTube Property Tours | Any YouTube URL | Dynamic | Interior accessibility — doorways, bathrooms, stairs |
| Sidewalk Semantic | [HuggingFace](https://huggingface.co/datasets/segments/sidewalk-semantic) | 1,000+ images | Optional — semantic segmentation of sidewalks |

---

## Custom Plugin: `@accesscheck/video-sampler`

Our novel FiftyOne plugin that converts any YouTube video or local video file into a curated image dataset with intelligent frame selection.

**Operators:**
- `sample_from_youtube` — YouTube URL → smart frames → FiftyOne dataset
- `sample_from_video` — Local video file → smart frames → FiftyOne dataset

**Features:**
- Scene-change detection (histogram-based)
- Perceptual deduplication (pHash)
- Configurable strategies: uniform, scene-change, hybrid
- Metadata preservation (source URL, timestamp, frame number)

---

## Existing Plugins Used

| Plugin | Role |
|---|---|
| `@AdonaiVera/gemini-vision-plugin` | VLM backbone for image analysis |
| `@voxel51/brain` | CLIP embeddings, similarity search, 2D visualization |
| `@voxel51/evaluation` | Accuracy metrics against ground truth |

---

## Team

Built at the Agents World Visual AI Hackathon at ASU, March 21, 2026.

---

## License

Apache 2.0
