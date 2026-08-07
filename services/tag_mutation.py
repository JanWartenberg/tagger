from dataclasses import dataclass, field
from typing import Callable

from exif_tool import ExifTool, KeywordState
from services.keyword_reconciliation import normalize_keywords


StateLoader = Callable[[str], KeywordState]
KeywordTransform = Callable[[str, KeywordState], list[str]]
StateTransform = Callable[[str, KeywordState], KeywordState]


@dataclass(frozen=True)
class TagMutationResult:
    updated_states: dict[str, KeywordState]
    emptiness_by_path: dict[str, bool]
    processed_count: int
    changed_count: int
    failed_paths: dict[str, str] = field(default_factory=dict)
    attempts_by_path: dict[str, int] = field(default_factory=dict)


class TagMutationService:
    def __init__(self, exif: ExifTool) -> None:
        self.exif = exif

    def add_tag(
        self,
        file_paths: list[str],
        tag: str,
        keep_backup: bool,
        load_state: StateLoader,
    ) -> TagMutationResult:
        return self.replace_keywords(
            file_paths,
            keep_backup,
            load_state,
            lambda _path, state: state.iptc + [tag],
        )

    def add_tags(
        self,
        file_paths: list[str],
        tags: list[str],
        keep_backup: bool,
        load_state: StateLoader,
    ) -> TagMutationResult:
        return self.replace_keywords(
            file_paths,
            keep_backup,
            load_state,
            lambda _path, state: state.iptc + tags,
        )

    def remove_tags(
        self,
        file_paths: list[str],
        tags_to_remove: set[str],
        keep_backup: bool,
        load_state: StateLoader,
    ) -> TagMutationResult:
        remove_casefold = {tag.casefold() for tag in tags_to_remove}
        return self.replace_keywords(
            file_paths,
            keep_backup,
            load_state,
            lambda _path, state: [
                tag for tag in state.iptc if tag.casefold() not in remove_casefold
            ],
        )

    def replace_keywords(
        self,
        file_paths: list[str],
        keep_backup: bool,
        load_state: StateLoader,
        transform: KeywordTransform,
    ) -> TagMutationResult:
        """Apply canonical-tag intent while preserving an intentionally empty XMP field."""
        return self.replace_keyword_states(
            file_paths,
            keep_backup,
            load_state,
            lambda path, state: self._ordinary_mutation_state(
                state, transform(path, state)
            ),
        )

    def replace_keyword_states(
        self,
        file_paths: list[str],
        keep_backup: bool,
        load_state: StateLoader,
        transform: StateTransform,
    ) -> TagMutationResult:
        updated_states: dict[str, KeywordState] = {}
        emptiness_by_path: dict[str, bool] = {}
        failed_paths: dict[str, str] = {}

        for path in file_paths:
            try:
                current = load_state(path)
                target = self._normalized_state(transform(path, current), current)
                self.exif.write_keyword_fields(
                    [path], target.iptc, target.xmp, keep_backup=keep_backup
                )
            except Exception as error:
                failed_paths[path] = str(error)
                continue
            updated_states[path] = target
            emptiness_by_path[path] = not target.iptc

        return TagMutationResult(
            updated_states=updated_states,
            emptiness_by_path=emptiness_by_path,
            processed_count=len(file_paths),
            changed_count=len(updated_states),
            failed_paths=failed_paths,
        )

    def resolve_keyword_fields(
        self,
        file_paths: list[str],
        chosen_states: dict[str, KeywordState],
        keep_backup: bool,
        load_state: StateLoader,
    ) -> TagMutationResult:
        """Write Resolve-dialog choices, retrying a field pair at most three times."""
        updated_states: dict[str, KeywordState] = {}
        emptiness_by_path: dict[str, bool] = {}
        failed_paths: dict[str, str] = {}
        attempts_by_path: dict[str, int] = {}

        for path in file_paths:
            chosen = chosen_states[path]
            target = self._normalized_state(chosen, chosen)
            attempts = 0
            try:
                # This fresh read intentionally does not merge external changes into
                # the dialog's explicit choices. If it fails, apply those choices.
                try:
                    load_state(path)
                except Exception:
                    pass
                for attempt in range(3):
                    attempts += 1
                    try:
                        self.exif.write_keyword_fields(
                            [path], target.iptc, target.xmp, keep_backup=keep_backup
                        )
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                else:  # pragma: no cover - the loop always breaks or raises
                    raise RuntimeError("Resolve write did not run")
            except Exception as error:
                failed_paths[path] = str(error)
                attempts_by_path[path] = attempts
                continue
            updated_states[path] = target
            emptiness_by_path[path] = not target.iptc

        return TagMutationResult(
            updated_states=updated_states,
            emptiness_by_path=emptiness_by_path,
            processed_count=len(file_paths),
            changed_count=len(updated_states),
            failed_paths=failed_paths,
            attempts_by_path=attempts_by_path,
        )

    @staticmethod
    def _ordinary_mutation_state(
        current: KeywordState, keywords: list[str]
    ) -> KeywordState:
        iptc = sorted(normalize_keywords(keywords), key=str.casefold)
        # S3 is deliberately silent: routine tag edits keep XMP empty rather
        # than recreating it as a mirror. Non-empty XMP remains a mirror.
        xmp = iptc if current.xmp else []
        return TagMutationService._state(current, iptc, xmp)

    @staticmethod
    def _normalized_state(target: KeywordState, fallback: KeywordState) -> KeywordState:
        return TagMutationService._state(
            fallback,
            list(normalize_keywords(target.iptc)),
            list(normalize_keywords(target.xmp)),
            iptc_readable=target.iptc_readable,
            xmp_readable=target.xmp_readable,
        )

    @staticmethod
    def _state(
        source: KeywordState,
        iptc: list[str],
        xmp: list[str],
        *,
        iptc_readable: bool | None = None,
        xmp_readable: bool | None = None,
    ) -> KeywordState:
        return KeywordState(
            iptc,
            xmp,
            source.date_original,
            source.date_create,
            source.date_xmp_create,
            source.date_digitized,
            source.iptc_readable if iptc_readable is None else iptc_readable,
            source.xmp_readable if xmp_readable is None else xmp_readable,
        )
