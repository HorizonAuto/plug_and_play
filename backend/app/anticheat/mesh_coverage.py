def check(mesh_summary: dict, min_faces: int = 5_000, min_anchors: int = 5) -> dict:
    total_faces = int(mesh_summary.get("totalFaces", 0))
    anchors = int(mesh_summary.get("anchorCount", 0))

    if total_faces == 0 and anchors == 0:
        return {
            "check": "mesh_coverage",
            "passed": None,
            "reason": "no LiDAR mesh data (non-Pro device or scan failed)",
        }

    enough_geometry = total_faces >= min_faces
    enough_anchors = anchors >= min_anchors
    passed = enough_geometry and enough_anchors

    return {
        "check": "mesh_coverage",
        "passed": passed,
        "reason": (
            f"{total_faces} mesh triangles across {anchors} anchors "
            + ("(adequate)" if passed else f"— need ≥{min_faces} triangles and ≥{min_anchors} anchors")
        ),
        "total_faces": total_faces,
        "anchor_count": anchors,
    }
