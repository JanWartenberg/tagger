from dataclasses import dataclass
from typing import Callable

from exif_tool import ExifTool, KeywordState
from utils import dedupe_casefold


StateLoader = Callable[[str], KeywordState]
KeywordTransform = Callable[[str, KeywordState], list[str]]


@dataclass(frozen=True)
class TagMutationResult:
    updated_states: dict[str, KeywordState]
    emptiness_by_path: dict[str, bool]
    processed_count: int
    changed_count: int


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
            lambda _path, state: state.merged + [tag],
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
            lambda _path, state: state.merged + tags,
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
            lambda _path, state: [tag for tag in state.merged if tag.casefold() not in remove_casefold],
        )

    def replace_keywords(
        self,
        file_paths: list[str],
        keep_backup: bool,
        load_state: StateLoader,
        transform: KeywordTransform,
    ) -> TagMutationResult:
        updated_states: dict[str, KeywordState] = {}
        emptiness_by_path: dict[str, bool] = {}

        for path in file_paths:
            current = load_state(path)
            keywords = self._normalize_keywords(transform(path, current))
            self.exif.write_keywords([path], keywords, keep_backup=keep_backup)
            updated_state = self._state_with_keywords(current, keywords)
            updated_states[path] = updated_state
            emptiness_by_path[path] = len(keywords) == 0

        return TagMutationResult(
            updated_states=updated_states,
            emptiness_by_path=emptiness_by_path,
            processed_count=len(file_paths),
            changed_count=len(file_paths),
        )

    def resolve_mismatches(
        self,
        file_paths: list[str],
        keep_backup: bool,
    ) -> TagMutationResult:
        updated_states: dict[str, KeywordState] = {}
        emptiness_by_path: dict[str, bool] = {}
        changed_count = 0

        for path in file_paths:
            current = self.exif.read_keywords(path)
            keywords = self._normalize_keywords(current.merged)
            if current.mismatch:
                self.exif.write_keywords([path], keywords, keep_backup=keep_backup)
                changed_count += 1
            updated_state = self._state_with_keywords(current, keywords)
            updated_states[path] = updated_state
            emptiness_by_path[path] = len(keywords) == 0

        return TagMutationResult(
            updated_states=updated_states,
            emptiness_by_path=emptiness_by_path,
            processed_count=len(file_paths),
            changed_count=changed_count,
        )

    def _normalize_keywords(self, keywords: list[str]) -> list[str]:
        normalized = dedupe_casefold([keyword.strip() for keyword in keywords if keyword.strip()])
        normalized.sort(key=lambda value: value.casefold())
        return normalized

    def _state_with_keywords(self, current: KeywordState, keywords: list[str]) -> KeywordState:
        return KeywordState(
            keywords,
            keywords,
            current.date_original,
            current.date_create,
            current.date_xmp_create,
            current.date_digitized,
        )
