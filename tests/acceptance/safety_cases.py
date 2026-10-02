"""Real-file refusal scenarios at the approved propagation/mutation seams."""

import os
from pathlib import Path

from PyQt6 import QtWidgets

from confirmed_copy import cli, emit, generate_photos, metadata, photo_hashes, tags
from tagger_app.exif_tool import ExifTool, ExifToolError, KeywordState
from tagger_app.services.duplicate_detection import (
    ExifToolCaptureMetadataReader,
    SameCaptureTimestampDetector,
    ScanRequest,
)
from tagger_app.services.tag_mutation import TagMutationService
from tagger_app.services.tag_propagation import (
    TagPropagationPlan,
    prepare_propagation,
    require_empty_target,
    validate_propagation,
)


def refusal_case(root: Path, role: str, change: str, stage: str, backup: bool) -> None:
    case = f"{stage}_{change}_{role}_refused"
    photos = root / case
    generate_photos(photos)
    exif = ExifTool()
    result = SameCaptureTimestampDetector().scan(
        ScanRequest(case, tuple(str(path) for path in photos.glob("*.jpg"))),
        ExifToolCaptureMetadataReader(exif),
    )
    assert result.complete and not result.errors and len(result.groups) == 1
    source = str(photos / "source.jpg")
    targets = (str(photos / "mirror.jpg"),)

    def prepare() -> TagPropagationPlan:
        return prepare_propagation(
            result,
            result.groups[0].group_id,
            source,
            targets,
            backup,
            exif.read_keywords,
            lambda _path: None,
        )

    # Positive control: fresh, unchanged assessment must be accepted without writes.
    plan = prepare()
    validate_propagation(plan, result, exif.read_keywords, lambda _path: None)
    changed_path = photos / ("source.jpg" if role == "source" else "mirror.jpg")
    if change == "changed":
        cli("-overwrite_original", "-IPTC:Keywords=External", changed_path)
        assert tags(metadata(changed_path), "IPTC:Keywords") == ["External"]
    else:
        changed_path.unlink()
        assert not changed_path.exists()
    before = photo_hashes(photos)
    try:
        if stage == "preview":
            prepare()
        else:
            validate_propagation(plan, result, exif.read_keywords, lambda _path: None)
    except (ValueError, ExifToolError) as error:
        refusal = str(error)
        assert changed_path.name in refusal, refusal
        if change == "changed":
            assert isinstance(error, ValueError) and "Tags changed" in refusal, refusal
    else:
        raise AssertionError(f"Unsafe propagation accepted: {case}")
    assert photo_hashes(photos) == before, "Refusal wrote files or backups"
    emit(case, reason=refusal, before_sha256=before, after_sha256=photo_hashes(photos))


def write_guard_case(root: Path, change: str, backup: bool) -> None:
    case = f"write_{change}_target_refused"
    photos = root / case
    generate_photos(photos)
    target = str(photos / "mirror.jpg")
    exif = ExifTool()
    # The target is genuinely readable and empty before the external change.
    require_empty_target(exif.read_keywords(target))
    if change == "changed":
        cli("-overwrite_original", "-IPTC:Keywords=External", target)
        assert tags(metadata(Path(target)), "IPTC:Keywords") == ["External"]
    else:
        Path(target).unlink()
    before = photo_hashes(photos)

    def exact_copy(_path: str, state: KeywordState) -> list[str]:
        require_empty_target(state)
        return ["Holiday"]

    result = TagMutationService(exif).replace_keywords(
        [target],
        backup,
        exif.read_keywords,
        exact_copy,
    )
    assert result.processed_count == 1 and result.changed_count == 0
    assert not result.updated_states and set(result.failed_paths) == {target}
    assert result.failed_paths[target]
    assert photo_hashes(photos) == before, "Final write guard wrote files or backups"
    emit(
        case,
        failures=result.failed_paths,
        before_sha256=before,
        after_sha256=photo_hashes(photos),
    )


def run() -> None:
    if not __debug__:
        raise RuntimeError("Assertions must be enabled")
    app = QtWidgets.QApplication([])
    root = Path(os.environ["TAGGER_ACCEPTANCE_ROOT"])
    backup = os.environ["TAGGER_ACCEPTANCE_BACKUP"] == "on"
    phase = os.environ["TAGGER_ACCEPTANCE_PHASE"]
    if phase == "write-guard":
        for change in ("changed", "missing"):
            write_guard_case(root, change, backup)
    else:
        stage = phase.removeprefix("safety-")
        if stage not in ("preview", "confirm"):
            raise ValueError(f"Unknown safety phase: {phase}")
        for role in ("source", "target"):
            for change in ("changed", "missing"):
                refusal_case(root, role, change, stage, backup)
    app.quit()


if __name__ == "__main__":
    run()
