"""
AccessCheck — Scoring & Report Generation

Aggregates per-sample accessibility findings into an overall
property/dataset-level report.
"""

import json
import logging
from collections import Counter

from prompts import SEVERITY_WEIGHTS

logger = logging.getLogger(__name__)


def compute_accessibility_report(dataset):
    """
    Aggregate all accessibility audit results from a FiftyOne dataset
    into a comprehensive report.

    Args:
        dataset: a FiftyOne dataset with audit fields populated

    Returns:
        dict with report data
    """
    scores = []
    all_issues = []
    severity_counts = Counter()
    issue_type_counts = Counter()
    scene_type_counts = Counter()
    accessible_count = 0
    inaccessible_count = 0
    worst_samples = []

    for sample in dataset:
        if sample.get("audit_status") != "success":
            continue

        score = sample.get("accessibility_score")
        if score is not None:
            scores.append(score)
            worst_samples.append({
                "filepath": sample.filepath,
                "score": score,
                "scene_type": sample.get("scene_type", "unknown"),
                "issue_count": sample.get("issue_count", 0),
            })

        if sample.get("overall_accessible"):
            accessible_count += 1
        else:
            inaccessible_count += 1

        scene = sample.get("scene_type", "unknown")
        scene_type_counts[scene] += 1

        # Parse issues
        issues_json = sample.get("issues_json", "[]")
        try:
            issues = json.loads(issues_json) if issues_json else []
        except json.JSONDecodeError:
            issues = []

        for issue in issues:
            severity = issue.get("severity", "minor")
            issue_type = issue.get("issue_type", "other")
            severity_counts[severity] += 1
            issue_type_counts[issue_type] += 1
            all_issues.append(issue)

    # Compute overall score
    overall_score = round(sum(scores) / len(scores), 1) if scores else None

    # Top 5 worst samples
    worst_samples.sort(key=lambda x: x["score"])
    top_5_worst = worst_samples[:5]

    # Remediation priority: severity_weight * frequency
    remediation_priority = []
    for issue_type, count in issue_type_counts.most_common():
        # Find the most common severity for this issue type
        severities = [
            i.get("severity", "minor")
            for i in all_issues
            if i.get("issue_type") == issue_type
        ]
        avg_weight = sum(SEVERITY_WEIGHTS.get(s, 1.0) for s in severities) / len(severities)
        priority_score = avg_weight * count

        # Get a sample remediation suggestion
        sample_remediation = next(
            (i.get("remediation", "N/A") for i in all_issues if i.get("issue_type") == issue_type),
            "N/A",
        )
        remediation_priority.append({
            "issue_type": issue_type,
            "count": count,
            "avg_severity_weight": round(avg_weight, 2),
            "priority_score": round(priority_score, 2),
            "remediation": sample_remediation,
        })

    remediation_priority.sort(key=lambda x: x["priority_score"], reverse=True)

    report = {
        "overall_score": overall_score,
        "total_samples_audited": len(scores),
        "accessible_count": accessible_count,
        "inaccessible_count": inaccessible_count,
        "total_issues_found": len(all_issues),
        "severity_breakdown": {
            "critical": severity_counts.get("critical", 0),
            "major": severity_counts.get("major", 0),
            "minor": severity_counts.get("minor", 0),
        },
        "issues_by_type": dict(issue_type_counts.most_common()),
        "issues_by_scene": dict(scene_type_counts.most_common()),
        "top_5_worst_locations": top_5_worst,
        "remediation_priority": remediation_priority[:10],
    }

    return report


def print_report(report):
    """Pretty-print the accessibility report to console."""

    print("\n" + "=" * 70)
    print("  ACCESSCHECK — ACCESSIBILITY AUDIT REPORT")
    print("=" * 70)

    score = report["overall_score"]
    if score is not None:
        bar_len = int(score / 2)
        bar = "█" * bar_len + "░" * (50 - bar_len)
        grade = (
            "A (Excellent)" if score >= 90 else
            "B (Good)" if score >= 75 else
            "C (Needs Improvement)" if score >= 60 else
            "D (Poor)" if score >= 40 else
            "F (Critical)"
        )
        print(f"\n  Overall Accessibility Score: {score}/100  [{grade}]")
        print(f"  [{bar}]")
    else:
        print("\n  Overall Score: N/A (no samples audited)")

    print(f"\n  Samples Audited: {report['total_samples_audited']}")
    print(f"  Accessible:     {report['accessible_count']}")
    print(f"  Inaccessible:   {report['inaccessible_count']}")

    print(f"\n  Total Issues Found: {report['total_issues_found']}")
    sev = report["severity_breakdown"]
    print(f"    🔴 Critical: {sev['critical']}")
    print(f"    🟡 Major:    {sev['major']}")
    print(f"    🟢 Minor:    {sev['minor']}")

    if report["issues_by_type"]:
        print("\n  Top Issue Types:")
        for issue_type, count in list(report["issues_by_type"].items())[:8]:
            print(f"    • {issue_type}: {count}")

    if report["top_5_worst_locations"]:
        print("\n  Worst Locations (lowest scores):")
        for loc in report["top_5_worst_locations"]:
            name = loc["filepath"].split(os.sep)[-1] if os.sep in loc["filepath"] else loc["filepath"].split("/")[-1]
            print(f"    • {name} — Score: {loc['score']}, Issues: {loc['issue_count']} ({loc['scene_type']})")

    if report["remediation_priority"]:
        print("\n  Remediation Priority (fix these first):")
        for i, item in enumerate(report["remediation_priority"][:5], 1):
            print(f"    {i}. {item['issue_type']} (x{item['count']}, priority: {item['priority_score']})")
            print(f"       → {item['remediation']}")

    print("\n" + "=" * 70)


# Need os for the print_report function
import os
