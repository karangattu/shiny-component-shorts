"""Real media checks for editorial timelines and backwards-compatible assembly."""

import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/skills/shiny-component-shorts/scripts"))
import batch_process
import generate_tts
import generate_local_voice
import stitch_reel as reel


@pytest.fixture
def segment(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    audio = artifacts / "narration.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        stream.writeframes(
            b"".join(
                struct.pack("<h", int(1000 * math.sin(i * 0.1))) for i in range(48000)
            )
        )
    timing = {
        "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "duration_seconds": 2.0,
        "words": [
            {"word": "first", "start": 0.0, "end": 0.4, "sentence": 0},
            {"word": "second", "start": 1.0, "end": 1.4, "sentence": 1},
        ],
        "transcript_check": {"word_error_rate": 0, "vocalizations": []},
    }
    (artifacts / "narration-timing.json").write_text(json.dumps(timing))
    for name, color in [("first", "red"), ("second", "blue")]:
        Image.new("RGB", (128, 128), color).save(tmp_path / f"{name}.png")
    config = {
        "shots": [
            {
                "cue": name,
                "source": "A real source",
                "views": {
                    orientation: {"file": f"{name}.png", "fit": "contain"}
                    for orientation in ("vertical", "horizontal")
                },
            }
            for name in ("first", "second")
        ]
    }
    (tmp_path / "editorial.yaml").write_text(yaml.safe_dump(config))
    return tmp_path


def change(segment, edit):
    path = segment / "editorial.yaml"
    config = yaml.safe_load(path.read_text())
    edit(config)
    path.write_text(yaml.safe_dump(config))


def test_phrase_cues_include_audio_offset_and_one_second_tail(segment):
    plan = reel.editorial_plan(segment, "vertical")
    assert [shot["start"] for shot in plan["shots"]] == [0.0, 35 / 30]
    assert plan["duration"] == 95 / 30
    assert plan["shots"][0]["end"] == 35 / 30
    assert plan["shots"][1]["end"] == 95 / 30


@pytest.mark.parametrize(
    "edit, message",
    [
        (lambda c: c["shots"][0]["views"].pop("horizontal"), "horizontal"),
        (
            lambda c: c["shots"][0]["views"]["vertical"].update(file="missing.png"),
            "Missing",
        ),
        (lambda c: c["shots"][0]["views"]["vertical"].update(fit="stretch"), "fit"),
        (lambda c: c["shots"][1].update(cue="not spoken"), "spoken"),
        (lambda c: c["shots"][1].update(cue="first"), "order"),
        (
            lambda c: c["shots"][0]["views"]["vertical"].update(
                highlight=[0.9, 0, 0.2, 0.2]
            ),
            "highlight",
        ),
        (
            lambda c: c["shots"][0]["views"]["vertical"].update(crop=[0, 0, 0, 1]),
            "crop",
        ),
    ],
)
def test_rejects_invalid_shots_before_rendering(segment, edit, message):
    change(segment, edit)
    with pytest.raises(ValueError, match=message):
        reel.editorial_plan(segment, "vertical")


def test_stale_narration_timing_is_rejected(segment):
    audio = segment / "artifacts/narration.wav"
    audio.write_bytes(audio.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="timing"):
        reel.editorial_plan(segment, "vertical")


def test_video_must_cover_shot_at_original_speed(segment):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=128x128:r=30:d=0.5",
            str(segment / "short.mp4"),
        ],
        check=True,
    )
    change(
        segment, lambda c: c["shots"][0]["views"]["vertical"].update(file="short.mp4")
    )
    with pytest.raises(ValueError, match="footage"):
        reel.editorial_plan(segment, "vertical")


def test_editorial_projects_are_found_for_narration_only(segment):
    assert batch_process.is_project(segment, explainers=True)
    assert not batch_process.is_project(segment, explainers=False)


def probe(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def pixel(video, second):
    frame = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(second),
            "-i",
            str(video),
            "-vf",
            "crop=2:2:iw/2:ih/2,scale=1:1",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return tuple(frame.stdout)


def test_editorial_build_has_real_hard_cuts_and_invalidates_changed_assets(
    segment, monkeypatch
):
    monkeypatch.setattr(
        reel, "SIZES", {"vertical": (144, 256), "horizontal": (256, 144)}
    )
    # One second of blue followed by two seconds of green proves the video in
    # point and original playback speed, alongside the still-image first shot.
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=128x128:r=30:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=lime:s=128x128:r=30:d=2",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            str(segment / "source.mp4"),
        ],
        check=True,
    )
    change(
        segment,
        lambda c: [
            view.update(file="source.mp4", **{"in": 0.5})
            for view in c["shots"][1]["views"].values()
        ],
    )
    config = {
        "style": "editorial",
        "title": "A small test",
        "features": [{"title": "Evidence", "dir": "."}],
    }
    (segment / "reel.yaml").write_text(yaml.safe_dump(config))
    for orientation, dimensions in [
        ("vertical", (288, 512)),
        ("horizontal", (512, 288)),
    ]:
        report = reel.build(segment, orientation)
        video = Path(report["reel"])
        metadata = probe(video)
        v = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        a = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
        assert (v["width"], v["height"]) == dimensions
        assert v["r_frame_rate"] == "30/1"
        assert a["sample_rate"] == "48000"
        assert abs(float(metadata["format"]["duration"]) - 95 / 30) < 0.05
        assert [c["label"] for c in report["chapters"]] == ["Evidence"]
        assert report["chapters"][0]["start"] == 0
        assert pixel(video, 1.10)[0] > 200
        assert pixel(video, 1.20)[2] > 200
        assert pixel(video, 1.80)[1] > 200
    Image.new("RGB", (128, 128), "lime").save(segment / "first.png")
    changed = reel.build(segment, "vertical")
    assert pixel(Path(changed["reel"]), 0.5)[1] > 200


def test_legacy_reel_keeps_cards_and_transitions(segment, monkeypatch):
    monkeypatch.setattr(reel, "SIZES", {"vertical": (72, 128), "horizontal": (128, 72)})
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=144x256:r=30:d=1",
            str(segment / "artifacts/demo.mp4"),
        ],
        check=True,
    )
    (segment / "editorial.yaml").unlink()
    (segment / "reel.yaml").write_text(
        yaml.safe_dump({"features": [{"title": "Original", "dir": "."}]})
    )
    report = reel.build(segment, "vertical")
    assert [c["label"] for c in report["chapters"]] == [
        "Intro",
        "Feature 1 card",
        "Original",
    ]
    assert report["duration_seconds"] == pytest.approx(8.5, abs=0.1)


def test_join_preserves_segment_duration_and_cuts_without_audio_overlap(tmp_path):
    clips = []
    for index, (color, frequency) in enumerate([("red", 440), ("blue", 880)]):
        path = tmp_path / f"clip-{index}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color={color}:s=128x128:r=30:d=1",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration=1",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-shortest",
                str(path),
            ],
            check=True,
        )
        clips.append((path, 1.0, "cut"))
    output = tmp_path / "joined.mp4"
    assert reel.join(clips, output) == [0.0, 1.0]
    assert float(probe(output)["format"]["duration"]) == pytest.approx(2.0, abs=0.025)
    assert pixel(output, 0.95)[0] > 200
    assert pixel(output, 1.05)[2] > 200


def test_invalid_style_does_not_silently_use_legacy(segment):
    (segment / "reel.yaml").write_text(
        yaml.safe_dump(
            {"style": "editoral", "features": [{"title": "Test", "dir": "."}]}
        )
    )
    with pytest.raises(ValueError, match="style"):
        reel.load_reel(segment)


def test_editorial_narration_is_not_squeezed_to_reel_length(segment):
    parent = segment.parent / "reel.yaml"
    parent.write_text("style: editorial\n")
    timing = segment / "artifacts/narration-timing.json"
    timing.write_text(json.dumps({"duration_seconds": 90}))
    assert batch_process.reel_segment_warnings(segment, timing) == []
    (segment / "editorial.yaml").unlink()
    assert batch_process.reel_segment_warnings(segment, timing)


def test_long_editorial_scripts_keep_validation_without_short_word_quota():
    prompt = (
        "Audio profile: Calm developer\nScene: Real tests\nDirector's notes: Natural pauses\nTranscript:\n"
        + "This shows the test result. " * 40
    )
    assert generate_tts.validate_narration_prompt(prompt, editorial=True) == []
    assert generate_tts.validate_narration_prompt(prompt)
    assert generate_tts.validate_narration_prompt(prompt + "[laughing]", editorial=True)
    assert generate_tts.validate_narration_prompt(
        prompt.split("Transcript:")[0] + "Transcript:", editorial=True
    )


def test_editorial_synthesis_selects_long_script_validation(segment):
    command = batch_process.synthesis_command(
        segment,
        {},
        segment / "artifacts/narration.txt",
        segment / "artifacts/narration.wav",
        segment / "artifacts/usage.json",
    )
    assert "--editorial" in command
    local_command = batch_process.synthesis_command(
        segment,
        {
            "provider": "local-voice-cloning",
            "reference_voice": str(segment / "artifacts/narration.wav"),
            "engine_dir": str(segment),
        },
        segment / "artifacts/narration.txt",
        segment / "artifacts/narration.wav",
        segment / "artifacts/usage.json",
    )
    assert generate_local_voice.parse_args(local_command[2:]).editorial
    (segment / "editorial.yaml").unlink()
    command = batch_process.synthesis_command(
        segment,
        {},
        segment / "artifacts/narration.txt",
        segment / "artifacts/narration.wav",
        segment / "artifacts/usage.json",
    )
    assert "--editorial" not in command


def test_separate_series_resets_each_video_and_preserves_combined_export(
    segment, monkeypatch
):
    monkeypatch.setattr(
        reel, "SIZES", {"vertical": (144, 256), "horizontal": (256, 144)}
    )
    shutil.copytree(segment, segment / "other", ignore=shutil.ignore_patterns("other"))
    config = {
        "style": "editorial",
        "features": [
            {"title": "First point", "dir": "."},
            {"title": "Second point", "dir": "other"},
        ],
    }
    (segment / "reel.yaml").write_text(yaml.safe_dump(config))
    combined = segment / "artifacts/reel.mp4"
    combined.write_bytes(b"preserve the existing export")
    reports = reel.build_series(segment)
    assert len(reports) == 4
    assert combined.read_bytes() == b"preserve the existing export"
    assert [report["orientation"] for report in reports] == [
        "vertical",
        "horizontal",
        "vertical",
        "horizontal",
    ]
    for report, title in zip(
        reports, ["First point", "First point", "Second point", "Second point"]
    ):
        assert [c["label"] for c in report["chapters"]] == [title]
        assert report["chapters"][0]["start"] == 0
        assert Path(report["reel"]).is_file()
        assert float(
            probe(Path(report["reel"]))["format"]["duration"]
        ) == pytest.approx(95 / 30, abs=0.05)
    assert (
        len(json.loads((segment / "artifacts/series.json").read_text())["videos"]) == 4
    )


def test_separate_series_is_not_limited_by_combined_reel_feature_count(segment):
    (segment / "reel.yaml").write_text(
        yaml.safe_dump(
            {
                "style": "editorial",
                "features": [{"title": f"Point {n}", "dir": "."} for n in range(7)],
            }
        )
    )
    assert len(reel.load_reel(segment, separate=True)["features"]) == 7
    with pytest.raises(SystemExit):
        reel.load_reel(segment)


def test_fixed_overview_duration_holds_last_still_and_rejects_short_target(segment):
    change(segment, lambda c: c.update(target_seconds=5))
    plan = reel.editorial_plan(segment, 'vertical')
    assert plan['duration'] == 5 and plan['shots'][-1]['end'] == 5
    change(segment, lambda c: c.update(target_seconds=2))
    with pytest.raises(ValueError, match='narration'):
        reel.editorial_plan(segment, 'vertical')
    for value in [True, float('nan'), 5.01]:
        change(segment, lambda c: c.update(target_seconds=value))
        with pytest.raises(ValueError, match='target_seconds'):
            reel.editorial_plan(segment, 'vertical')


def test_embedded_chapters_and_validator_reject_changed_evidence(segment, monkeypatch):
    import validate_editorial
    monkeypatch.setattr(reel, 'SIZES', {'vertical': (144,256), 'horizontal': (256,144)})
    change(segment, lambda c: c.update(target_seconds=4))
    change(segment, lambda c: c['shots'][0].update(chapter='First claim'))
    change(segment, lambda c: c['shots'][1].update(chapter='Second claim'))
    (segment/'reel.yaml').write_text(yaml.safe_dump({'style':'editorial','title':'Evidence','features':[{'title':'A feature','dir':'.'}]}))
    monkeypatch.chdir(segment)
    report = reel.build(Path('.'), 'vertical')
    data = json.loads(subprocess.run(['ffprobe','-v','error','-show_chapters','-show_streams','-of','json',report['reel']],capture_output=True,text=True,check=True).stdout)
    assert [c['tags']['title'] for c in data['chapters']] == ['First claim','Second claim']
    assert float(data['chapters'][1]['start_time']) == pytest.approx(35/30, abs=.001)
    video=next(s for s in data['streams'] if s['codec_type']=='video')
    assert int(video['nb_frames']) == 120
    monkeypatch.chdir(segment.parent)
    checked = validate_editorial.validate_report(report)
    assert checked['decode'] == 'passed' and checked['frames'] == 120
    Image.new('RGB',(128,128),'lime').save(segment/'first.png')
    with pytest.raises(ValueError, match='stale'):
        validate_editorial.validate_report(report)


def test_source_manifest_rejects_unrendered_code_edits(segment):
    source = segment / 'app.py'
    source.write_text('print(42)\n')
    manifest=segment/'source-manifest.json'
    manifest.write_text(json.dumps({'sources':[{'file':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}))
    change(segment,lambda c:c.update(source_manifest='source-manifest.json'))
    reel.editorial_plan(segment,'vertical')
    source.write_text('print(43)\n')
    with pytest.raises(ValueError,match='source.*changed|stale'):
        reel.editorial_plan(segment,'vertical')


def test_normalize_sets_an_explicit_output_frame_rate(tmp_path, monkeypatch):
    # With only fps= and -t, ffmpeg 8.1 drops a piece's final frame (29.99 fps).
    calls = []
    monkeypatch.setattr(reel, 'probe_duration', lambda path: 78.4)
    monkeypatch.setattr(reel, 'has_audio', lambda path: True)
    monkeypatch.setattr(reel.subprocess, 'run', lambda command, **kwargs: calls.append(command))
    reel._normalize(tmp_path / 'in.mp4', tmp_path / 'out.mp4', 'vertical')
    command = calls[0]
    assert command[command.index('-r') + 1] == str(reel.FPS)
