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
from tagger_app.services.pending_tag_mutation import (
    PendingTagMutationCoordinator,
    TagIntent,
)
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


def unreadable_mutation_case(root: Path, backup: bool) -> None:
    """Real ExifTool read errors refuse writes; repaired files support failed-only retry."""
    for operation in ("add", "remove", "paste", "retry"):
        photos = root / f"unreadable-{operation}"
        generate_photos(photos)
        path = str(photos / "source.jpg")
        healthy = str(photos / "empty-xmp.jpg")
        original = Path(path).read_bytes()
        # A fully truncated generated JPEG produces a real ExifTool read error.
        # Silent parser omissions are a separate limitation, not simulated here.
        Path(path).write_bytes(b"")
        before = photo_hashes(photos)
        exif = ExifTool()
        service = TagMutationService(exif)
        try:
            exif.read_keywords(path)
        except ExifToolError as error:
            read_error = str(error)
        else:
            raise AssertionError("Fixture must fail during metadata reading")
        intents = (
            [TagIntent.remove("Holiday")]
            if operation == "remove"
            else [TagIntent.add("Added")]
        )
        pending = PendingTagMutationCoordinator()
        pending.remember_confirmed(
            {path: KeywordState(["Holiday"], ["Source mirror only"])}
        )
        mutation = pending.begin_intents({path: intents})
        if operation == "add":
            result = service.add_tag([path], "Added", backup, exif.read_keywords)
        elif operation == "remove":
            result = service.remove_tags(
                [path], {"Holiday"}, backup, exif.read_keywords
            )
        elif operation == "paste":
            result = service.add_tags([path], ["Added"], backup, exif.read_keywords)
        else:
            result = service.replace_keyword_states(
                [path], backup, exif.read_keywords, mutation.apply
            )
        assert set(result.failed_paths) == {path} and not result.updated_states
        assert result.failed_paths[path] == read_error
        assert photo_hashes(photos) == before, "Unreadable mutation wrote bytes/backups"
        pending.fail(mutation, list(result.failed_paths))

        # A mixed batch must still confirm its healthy photo.
        partial = service.add_tag(
            [path, healthy], "Healthy", backup, exif.read_keywords
        )
        assert set(partial.failed_paths) == {path}
        assert set(partial.updated_states) == {healthy}
        assert photo_hashes(photos)["source.jpg"] == before["source.jpg"]
        assert not Path(path + "_original").exists()
        healthy_before_retry = Path(healthy).read_bytes()

        # Repair is external; retry rereads it and preserves an external tag.
        Path(path).write_bytes(original)
        cli("-overwrite_original", "-IPTC:Keywords+=External", path)
        repaired = Path(path).read_bytes()
        retry = pending.retry_failed([path, healthy])
        assert retry is not None and set(retry.intents_by_path) == {path}
        result = service.replace_keyword_states(
            [path], backup, exif.read_keywords, retry.apply
        )
        assert not result.failed_paths and set(result.updated_states) == {path}
        expected = (
            ["External"] if operation == "remove" else ["Added", "External", "Holiday"]
        )
        record = metadata(Path(path))
        assert tags(record, "IPTC:Keywords") == expected
        assert tags(record, "XMP-dc:Subject") == expected
        assert Path(healthy).read_bytes() == healthy_before_retry
        if backup:
            assert Path(path + "_original").read_bytes() == repaired
        else:
            assert not Path(path + "_original").exists()
    emit(
        "unreadable_mutations_and_failed_only_retry",
        operations=["add", "remove", "paste", "retry"],
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
        unreadable_mutation_case(root, backup)
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
