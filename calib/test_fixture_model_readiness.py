#!/usr/bin/env python3
"""Pure-software readiness regressions for fixture_model_orchestrator.py.

No hardware, no capture, no DMX. These cover the final-run readiness fixes whose
failure mode would otherwise only appear after a long physical run has started.

Run: calib/.venv/bin/python calib/test_fixture_model_readiness.py
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
GLARE_STILLS = (
    ROOT / "captures" / "fixture_model" / "_camera_glare_check" / "glare_check_20260607_013024.jpg",
    ROOT / "captures" / "fixture_model" / "_camera_glare_check" / "glare_check_20260607_013335.jpg",
)


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "fixture_model_orchestrator_under_test",
        HERE / "fixture_model_orchestrator.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_dense():
    spec = importlib.util.spec_from_file_location(
        "dense_cue_breakpoints_under_test",
        HERE / "dense_cue_breakpoints.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


orch = _load_orchestrator()
dense = _load_dense()


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _expect_raises(fn, needle):
    try:
        fn()
    except Exception as exc:
        assert needle in str(exc), str(exc)
        return
    raise AssertionError(f"expected exception containing {needle!r}")


def _isolated_analysis_geometry(path):
    class _Ctx:
        def __enter__(self):
            self.old_orch_path = orch.ANALYSIS_GEOMETRY_PATH
            self.old_env_path = os.environ.get("VLN_ANALYSIS_GEOMETRY_PATH")
            orch.ANALYSIS_GEOMETRY_PATH = path
            os.environ["VLN_ANALYSIS_GEOMETRY_PATH"] = str(path)
            return self

        def __exit__(self, *_exc):
            orch.ANALYSIS_GEOMETRY_PATH = self.old_orch_path
            if self.old_env_path is None:
                os.environ.pop("VLN_ANALYSIS_GEOMETRY_PATH", None)
            else:
                os.environ["VLN_ANALYSIS_GEOMETRY_PATH"] = self.old_env_path

    return _Ctx()


def _draw_projection_boxes(im, *, bottom=570, color=(245, 245, 250), width=3):
    draw = ImageDraw.Draw(im)
    draw.rectangle([70, 160, 550, bottom], outline=color, width=width)
    draw.rectangle([660, 160, 1215, bottom], outline=color, width=width)
    return im


def test_missing_dense_root_uses_recorded_phase0_count():
    with tempfile.TemporaryDirectory() as d:
        old_model, old_dense = orch.MODEL_PATH, orch.EXISTING_DENSE_ROOT
        root = pathlib.Path(d)
        orch.MODEL_PATH = root / "fixture_model.json"
        orch.EXISTING_DENSE_ROOT = root / "missing_dense"
        try:
            model = orch.base_model()
            model["provenance"]["phase0_validated_existing_dense_rows"] = 118
            _write_json(orch.MODEL_PATH, model)
            result = orch.validate_existing_dense()
            assert result["existing_dense_rows"] == 118
            assert result["dense_root_present"] is False
            assert "prior phase0 validation" in result["note"]
        finally:
            orch.MODEL_PATH, orch.EXISTING_DENSE_ROOT = old_model, old_dense


def test_missing_dense_root_without_record_errors():
    with tempfile.TemporaryDirectory() as d:
        old_model, old_dense = orch.MODEL_PATH, orch.EXISTING_DENSE_ROOT
        root = pathlib.Path(d)
        orch.MODEL_PATH = root / "fixture_model.json"
        orch.EXISTING_DENSE_ROOT = root / "missing_dense"
        try:
            _expect_raises(orch.validate_existing_dense, "no prior phase0 validation")
        finally:
            orch.MODEL_PATH, orch.EXISTING_DENSE_ROOT = old_model, old_dense


def test_present_empty_dense_manifest_is_not_treated_as_missing():
    with tempfile.TemporaryDirectory() as d:
        old_model, old_dense = orch.MODEL_PATH, orch.EXISTING_DENSE_ROOT
        root = pathlib.Path(d)
        orch.MODEL_PATH = root / "fixture_model.json"
        orch.EXISTING_DENSE_ROOT = root / "dense"
        try:
            model = orch.base_model()
            model["provenance"]["phase0_validated_existing_dense_rows"] = 118
            _write_json(orch.MODEL_PATH, model)
            _write_jsonl(orch.EXISTING_DENSE_ROOT / "manifest.jsonl", [])
            _expect_raises(orch.validate_existing_dense, "found 0")
        finally:
            orch.MODEL_PATH, orch.EXISTING_DENSE_ROOT = old_model, old_dense


def test_phase6_cites_recorded_dense_count_when_analysis_root_absent():
    with tempfile.TemporaryDirectory() as d:
        old_model, old_manifest, old_checkpoint, old_dense = (
            orch.MODEL_PATH,
            orch.MANIFEST,
            orch.CHECKPOINT,
            orch.EXISTING_DENSE_ROOT,
        )
        root = pathlib.Path(d)
        orch.MODEL_PATH = root / "fixture_model.json"
        orch.MANIFEST = root / "manifest.jsonl"
        orch.CHECKPOINT = root / "checkpoint.json"
        orch.EXISTING_DENSE_ROOT = root / "missing_dense"
        try:
            model = orch.base_model()
            model["provenance"]["phase0_validated_existing_dense_rows"] = 118
            _write_json(orch.MODEL_PATH, model)
            _write_jsonl(orch.MANIFEST, [{"phase": "phase6_cue_validation", "folder": "x"}])
            result = orch.phase6_validate(False)
            assert result["captured_exact_vectors"] == 118
            assert result["captured_exact_vectors_source"] == "phase0_record_dense_root_absent"
            assert result["new_cue_validation_captures"] == 1
            assert result["buckets"]["unresolved"] == 119
        finally:
            orch.MODEL_PATH, orch.MANIFEST, orch.CHECKPOINT, orch.EXISTING_DENSE_ROOT = (
                old_model,
                old_manifest,
                old_checkpoint,
                old_dense,
            )


def test_session_budget_is_resume_safe_and_still_caps_new_captures():
    with tempfile.TemporaryDirectory() as d:
        old_manifest, old_baseline, old_cap = orch.MANIFEST, orch.SESSION_BASELINE_CAPTURES, orch.MAX_CAPTURES
        root = pathlib.Path(d)
        orch.MANIFEST = root / "manifest.jsonl"
        try:
            _write_jsonl(orch.MANIFEST, [])
            orch.SESSION_BASELINE_CAPTURES = 0
            orch.MAX_CAPTURES = 3
            orch.assert_capture_budget(3)
            _expect_raises(lambda: orch.assert_capture_budget(4), "capture cap would be exceeded")

            _write_jsonl(orch.MANIFEST, [{"folder": f"existing/{i}"} for i in range(100)])
            orch.SESSION_BASELINE_CAPTURES = 100
            orch.MAX_CAPTURES = 5
            orch.assert_capture_budget(5)
            _expect_raises(lambda: orch.assert_capture_budget(6), "capture cap would be exceeded")
        finally:
            orch.MANIFEST, orch.SESSION_BASELINE_CAPTURES, orch.MAX_CAPTURES = old_manifest, old_baseline, old_cap


def test_phase_case_counts_are_derived_from_current_code():
    all_base_dependent = {f"CH{ch}": "base_dependent" for ch in (5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19)}
    assert len(orch.phase1_cases()) == 2472
    assert len(orch.phase15_cases()) == 1848
    assert len(orch.phase2_cases()) == 29
    assert len(orch.phase3_cases({})) == 3664
    assert len(orch.phase3_cases({"phase1_5_verdicts": all_base_dependent})) == 3984
    assert len(orch.phase4_cases()) == 48
    assert len(orch.cue_validation_cases()) == 175


def _make_synthetic_video(path, fps):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:s=160x90:r={fps}",
        "-t", "1.000", "-an", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(path),
    ], check=True)


def test_ffprobe_fps_classifies_generated_30_and_60_fps_mp4s():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        video30 = root / "sample_30.mp4"
        video60 = root / "sample_60.mp4"
        _make_synthetic_video(video30, 30)
        _make_synthetic_video(video60, 60)
        assert abs(orch.ffprobe_fps(video30) - 30.0) < 0.5
        assert abs(orch.ffprobe_fps_counted(video30) - 30.0) < 0.5
        assert abs(orch.ffprobe_fps(video60) - 60.0) < 0.5
        assert abs(orch.ffprobe_fps_counted(video60) - 60.0) < 0.5


def test_ffprobe_fps_falls_back_to_decoded_count_when_header_count_missing():
    old_probe = orch._ffprobe_stream
    calls = []

    def fake_probe(_video, show_entries, *, count_frames=False):
        calls.append((show_entries, count_frames))
        if count_frames:
            return {"nb_read_frames": "30", "duration": "1.0"}
        return {"duration": "1.0", "avg_frame_rate": "60/1"}

    try:
        orch._ffprobe_stream = fake_probe
        assert orch.ffprobe_fps(pathlib.Path("missing_header_count.mp4")) == 30.0
        assert calls == [
            ("stream=nb_frames,avg_frame_rate,duration", False),
            ("stream=nb_read_frames,duration", True),
        ]
    finally:
        orch._ffprobe_stream = old_probe


def test_frame_strip_generation_is_default_off_but_opt_in():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        old_state = {
            "CAPTURE_ROOT": orch.CAPTURE_ROOT,
            "MANIFEST": orch.MANIFEST,
            "CHECKPOINT": orch.CHECKPOINT,
            "FRAME_STRIPS": orch.FRAME_STRIPS,
            "set_dmx": orch.set_dmx,
            "capture_video": orch.capture_video,
            "ffprobe_fps": orch.ffprobe_fps,
            "recover_fps": orch.recover_fps,
            "extract_frame": orch.extract_frame,
            "assert_not_desktop_capture": orch.assert_not_desktop_capture,
            "frame_stats": orch.frame_stats,
            "frame_strip": orch.frame_strip,
            "analyze_with_dense": orch.analyze_with_dense,
            "checkpoint": orch.checkpoint,
            "sleep": orch.time.sleep,
        }
        strip_calls = []

        def fake_extract_frame(_video, out, _ts=0.25):
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), "white").save(out)

        try:
            orch.CAPTURE_ROOT = root / "captures"
            orch.MANIFEST = root / "manifest.jsonl"
            orch.CHECKPOINT = root / "checkpoint.json"
            orch.set_dmx = lambda _frame: None
            orch.capture_video = lambda out, _duration: out.parent.mkdir(parents=True, exist_ok=True) or out.write_bytes(b"not-used-by-test")
            orch.ffprobe_fps = lambda _video: 60.0
            orch.recover_fps = lambda _label: (True, [60.0])
            orch.extract_frame = fake_extract_frame
            orch.assert_not_desktop_capture = lambda _still, _label: None
            orch.frame_stats = lambda _still: {"mean_luma": 100.0, "bright_pixels": 100, "blank": False}
            orch.frame_strip = lambda *args: strip_calls.append(args)
            orch.analyze_with_dense = lambda _entry: {"motion_type": "static", "blank": False}
            orch.checkpoint = lambda *_args, **_kwargs: None
            orch.time.sleep = lambda _seconds: None

            orch.set_frame_strips_enabled(False)
            case = orch.Case("phase_test", "group", "state_no_strip", {1: 220}, changed_channels={1: 220})
            row = orch.capture_one(case)
            assert row["frame_strip_enabled"] is False
            assert strip_calls == []
            assert (orch.CAPTURE_ROOT / case.rel_dir / "still.jpg").exists()

            orch.set_frame_strips_enabled(True)
            case = orch.Case("phase_test", "group", "state_with_strip", {1: 220}, changed_channels={1: 220})
            row = orch.capture_one(case)
            assert row["frame_strip_enabled"] is True
            assert len(strip_calls) == 1
        finally:
            orch.CAPTURE_ROOT = old_state["CAPTURE_ROOT"]
            orch.MANIFEST = old_state["MANIFEST"]
            orch.CHECKPOINT = old_state["CHECKPOINT"]
            orch.FRAME_STRIPS = old_state["FRAME_STRIPS"]
            orch.set_dmx = old_state["set_dmx"]
            orch.capture_video = old_state["capture_video"]
            orch.ffprobe_fps = old_state["ffprobe_fps"]
            orch.recover_fps = old_state["recover_fps"]
            orch.extract_frame = old_state["extract_frame"]
            orch.assert_not_desktop_capture = old_state["assert_not_desktop_capture"]
            orch.frame_stats = old_state["frame_stats"]
            orch.frame_strip = old_state["frame_strip"]
            orch.analyze_with_dense = old_state["analyze_with_dense"]
            orch.checkpoint = old_state["checkpoint"]
            orch.time.sleep = old_state["sleep"]


def test_analysis_mask_sane_rejects_broad_and_bottom_edge_masks():
    _expect_raises(
        lambda: orch.assert_analysis_mask_sane(
            {
                "blank": False,
                "bright_fraction": orch.ANALYSIS_MASK_MAX_BRIGHT_FRACTION + 0.01,
                "bbox": [0, 100, 1279, 620],
                "analysis_roi": [0, 100, 1280, 700],
            },
            "broad synthetic",
        ),
        "covers too much",
    )
    _expect_raises(
        lambda: orch.assert_analysis_mask_sane(
            {
                "blank": False,
                "bright_fraction": 0.01,
                "bbox": [70, 160, 550, 698],
                "analysis_roi": [0, 129, 1280, 700],
            },
            "bottom synthetic",
        ),
        "bottom ROI edge",
    )


def test_dim_line_at_shared_floor_is_preserved_on_dark_wall():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        still = root / "dim_line.png"
        with _isolated_analysis_geometry(root / "missing_analysis_geometry.json"):
            im = Image.new("RGB", (320, 180), (8, 8, 8))
            draw = ImageDraw.Draw(im)
            draw.line([20, 90, 300, 90], fill=(58, 58, 58), width=1)
            im.save(still)
            stats = orch.frame_stats(still)
            assert stats["blank"] is False, stats
            pts, _brightness, _colors = dense.bright_points(Image.open(still), threshold=orch.LASER_CORE_THRESHOLD_FLOOR)
            assert len(pts) >= 250


def test_box_anchored_geometry_derives_from_real_glare_stills():
    for still in GLARE_STILLS:
        geometry = orch.derive_analysis_geometry(still, write=False)
        assert len(geometry["boxes"]) == 2, geometry
        assert abs(geometry["combined_bbox"][3] - 575) <= 12, geometry
        assert 4 <= geometry["boundary_margin"]["actual_headroom_px"] <= 16, geometry
        assert 0.5 <= geometry["boundary_margin"]["actual_headroom_inches"] <= 1.0, geometry
        glare = geometry["glare_band"]
        if glare["detected"]:
            assert geometry["analysis_roi"][3] <= glare["start_y"] - glare["clearance_px"], geometry
        assert geometry["analysis_roi"][3] > geometry["combined_bbox"][3], geometry
        assert geometry["analysis_roi"][3] <= geometry["source_image_size"]["height"], geometry


def test_geometry_reference_base_is_the_boundary_box_look_not_the_line():
    # Geometry/ROI must be derived from the max-size rectangular boundary-box
    # look (CH3=0, CH4 in 60-64, CH5=0, CH6/CH7=128, CH17=0), never the
    # PRIMARY_BASE "line" look, which does not trace boxes.
    base = orch.GEOMETRY_REFERENCE_BASE
    assert base[1] > 0, base
    assert base[3] == 0, base
    assert 60 <= base[4] <= 64, base
    assert base[5] == 0, base
    assert base[6] == 128 and base[7] == 128, base
    assert base[17] == 0, base
    assert orch.PRIMARY_BASE[3] != 0, "PRIMARY_BASE must stay the capture baseline (line look)"
    assert orch.PRIMARY_BASE[5] == 90, "PRIMARY_BASE must stay the CH5=90 capture baseline"


def test_geometry_reference_frame_selector_avoids_incomplete_scan_phase():
    video = ROOT / "captures" / "fixture_model" / "preflight" / "geometry_frame.mp4"
    if not video.exists():
        return
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        geom_path = root / "analysis_geometry.json"
        with _isolated_analysis_geometry(geom_path):
            still = root / "geometry_frame.jpg"
            geometry = orch.select_geometry_reference_frame(video, still)
            assert still.exists(), still
            assert len(geometry["boxes"]) == 2, geometry
            assert not geometry["boundary_margin"]["roi_boundary_glare_conflict"], geometry
            assert not any("width detection differs" in warning for warning in geometry["warnings"]), geometry
            cross = geometry["geometry_cross_check"]
            assert cross["left_width_relative_error"] < 0.25, geometry
            assert cross["right_width_relative_error"] < 0.25, geometry


def test_geometry_reference_mask_threshold_never_exceeds_pixel_range():
    still = ROOT / "captures" / "fixture_model" / "preflight" / "geometry_frame.jpg"
    if not still.exists():
        return
    stats = orch.frame_stats(still)
    assert stats["laser_core_threshold"] <= 255.0, stats
    assert stats["blank"] is False, stats
    assert stats["bright_pixels"] > 20, stats


def test_line_look_is_rejected_by_box_detection():
    # A thin horizontal dashed line (the PRIMARY_BASE look) must NOT be accepted
    # as a projection box; detection must fail loudly so preflight fails safe.
    with tempfile.TemporaryDirectory() as d:
        still = pathlib.Path(d) / "line_look.jpg"
        im = Image.new("RGB", (1280, 720), (96, 94, 92))
        px = im.load()
        for cx0, cx1 in ((150, 390), (575, 845)):
            for x in range(cx0, cx1, 26):
                for dx in range(0, 12):
                    for dy in range(-2, 3):
                        px[x + dx, 285 + dy] = (40, 90, 250)
        im.save(still)
        _expect_raises(lambda: orch.detect_projection_boxes(still), "found")


def test_geometry_clip_flag_fires_only_when_mask_reaches_derived_roi_bottom():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        geom_path = root / "analysis_geometry.json"
        with _isolated_analysis_geometry(geom_path):
            geometry = orch.derive_analysis_geometry(GLARE_STILLS[1], write=True)
            static_stats = orch.frame_stats(GLARE_STILLS[1])
            assert static_stats["geometry_clipped_low"] is False, static_stats

            roi_bottom = geometry["analysis_roi"][3]
            clipped = Image.new("RGB", (1280, 720), (20, 20, 20))
            draw = ImageDraw.Draw(clipped)
            draw.line([70, roi_bottom - 1, 1215, roi_bottom - 1], fill=(250, 250, 250), width=3)
            clipped_path = root / "clipped.png"
            clipped.save(clipped_path)
            clipped_stats = orch.frame_stats(clipped_path)
            assert clipped_stats["geometry_clipped_low"] is True, clipped_stats


def test_laser_core_mask_rejects_wall_bloom_and_bottom_reflection():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        still = root / "bloomy_static_reference.jpg"
        geom_path = root / "analysis_geometry.json"
        with _isolated_analysis_geometry(geom_path):
            reference = root / "geometry_reference.png"
            ref = Image.new("RGB", (1280, 720), (118, 116, 112))
            _draw_projection_boxes(ref, bottom=570)
            ref_px = ref.load()
            for y in range(650, 720):
                for x in range(0, 1280):
                    ref_px[x, y] = (170, 130, 210)
            ref.save(reference)
            orch.derive_analysis_geometry(reference, write=True)

        im = Image.new("RGB", (1280, 720), (118, 116, 112))
        px = im.load()
        # Soft laser bloom / room-lit wall: broad and intentionally above the old
        # fixed mx>110 branch that previously classified most of the wall.
        for y in range(130, 650):
            for x in range(0, 1280):
                px[x, y] = (132, 130, 126)
        # Two thin projection boxes.
        for x in range(70, 550):
            for dy in range(-1, 2):
                px[x, 160 + dy] = (245, 245, 250)
                px[x, 570 + dy] = (245, 245, 250)
        for y in range(160, 571):
            for dx in range(-1, 2):
                px[70 + dx, y] = (245, 245, 250)
                px[550 + dx, y] = (245, 245, 250)
        for x in range(660, 1215):
            for dy in range(-1, 2):
                px[x, 160 + dy] = (245, 245, 250)
                px[x, 570 + dy] = (245, 245, 250)
        for y in range(160, 571):
            for dx in range(-1, 2):
                px[660 + dx, y] = (245, 245, 250)
                px[1215 + dx, y] = (245, 245, 250)
        # Table reflection below useful projection area. The derived geometry ROI
        # should keep this from becoming the geometry bbox.
        for y in range(650, 720):
            for x in range(0, 1280):
                px[x, y] = (170, 130, 210)
        im.save(still)

        with _isolated_analysis_geometry(geom_path):
            stats = orch.frame_stats(still)
            assert stats["blank"] is False
            assert stats["bright_fraction"] < 0.08, stats
            assert stats["geometry_clipped_low"] is False, stats
            assert stats["bbox"][3] < stats["analysis_roi"][3] - orch.ANALYSIS_ROI_EDGE_MARGIN_PX, stats
            orch.assert_analysis_mask_sane(stats, "synthetic bloom reference")

            roi = stats["analysis_roi"]
            roi_pixels = (roi[2] - roi[0]) * (roi[3] - roi[1])
            pts, _brightness, _colors = dense.bright_points(Image.open(still), threshold=58)
            assert 20 < len(pts) < roi_pixels * 0.08


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"ok   {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
