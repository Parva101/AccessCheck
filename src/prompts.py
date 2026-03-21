"""
AccessCheck — Accessibility Audit Prompts

Contains the prompt templates for the VLM accessibility analysis.
Modify these prompts to tune the agent's behavior.
"""

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
  "overall_accessible": true or false,
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


SCENE_CLASSIFICATION_PROMPT = """
Look at this image and classify the scene type.
Respond with ONLY one of these values:
entrance, hallway, bathroom, kitchen, sidewalk, parking, stairway, bedroom, outdoor_path, living_room, other, not_applicable
"""


# Issue type definitions — used for tagging and reporting
ISSUE_TYPES = [
    "missing_ramp",
    "narrow_doorway",
    "stairs_only_access",
    "no_grab_bars",
    "blocked_pathway",
    "no_curb_cut",
    "high_counter",
    "poor_lighting",
    "no_tactile_paving",
    "steep_slope",
    "no_elevator_access",
    "inaccessible_parking",
    "obstructed_sidewalk",
    "no_handrail",
    "heavy_door",
    "no_accessible_signage",
    "uneven_surface",
    "other",
]

SEVERITY_LEVELS = ["critical", "major", "minor"]

SEVERITY_WEIGHTS = {
    "critical": 3.0,
    "major": 2.0,
    "minor": 1.0,
}
