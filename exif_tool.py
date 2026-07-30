import json
import shutil
import subprocess
from dataclasses import dataclass

from utils import dedupe_casefold, normalize_path


@dataclass
class KeywordState:
    iptc: list[str]
    xmp: list[str]
    date_original: str | None = None
    date_create: str | None = None
    date_xmp_create: str | None = None
    date_digitized: str | None = None

    @property
    def iptc_set(self) -> set[str]:
        return {k for k in self.iptc if k.strip()}

    @property
    def xmp_set(self) -> set[str]:
        return {k for k in self.xmp if k.strip()}

    @property
    def merged(self) -> list[str]:
        merged = list(self.iptc_set | self.xmp_set)
        merged = dedupe_casefold(merged)
        merged.sort(key=lambda s: s.casefold())
        return merged

    @property
    def mismatch(self) -> bool:
        return self.iptc_set != self.xmp_set

    @property
    def date_display(self) -> str:
        if self.date_original:
            return self.date_original
        if self.date_create:
            return self.date_create
        if self.date_xmp_create:
            return self.date_xmp_create
        if self.date_digitized:
            return self.date_digitized
        return ""


class ExifToolError(RuntimeError):
    pass


class ExifTool:
    def __init__(self, exe: str = "exiftool"):
        resolved = shutil.which(exe)
        if resolved:
            self.exe = resolved
        else:
            self.exe = exe

    def _run(self, args: list[str]) -> str:
        try:
            p = subprocess.run(
                [self.exe, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as e:
            raise ExifToolError(
                "exiftool not found on PATH. Install it and ensure `exiftool -ver` works."
            ) from e
        if p.returncode != 0:
            stderr = (p.stderr or "").strip()
            raise ExifToolError(stderr or f"exiftool failed with exit code {p.returncode}")
        return p.stdout

    def read_keywords(self, file_path: str) -> KeywordState:
        file_path = normalize_path(file_path)
        return self.read_keywords_many([file_path]).get(file_path, KeywordState([], []))

    def _parse_keyword_record(self, rec: dict) -> tuple[str | None, KeywordState]:
        src = rec.get("SourceFile")
        if not isinstance(src, str):
            return None, KeywordState([], [])

        iptc = rec.get("IPTC:Keywords", [])
        xmp = rec.get("XMP-dc:Subject", [])
        if isinstance(iptc, str):
            iptc = [iptc]
        if isinstance(xmp, str):
            xmp = [xmp]

        def _clean(v: object) -> list[str]:
            if not isinstance(v, list):
                return []
            out2: list[str] = []
            for x in v:
                if isinstance(x, str) and x.strip():
                    out2.append(x.strip())
            return out2

        def _first_str(keys: list[str]) -> str | None:
            for k in keys:
                v = rec.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, list) and v:
                    v0 = v[0]
                    if isinstance(v0, str) and v0.strip():
                        return v0.strip()
            return None

        state = KeywordState(
            _clean(iptc),
            _clean(xmp),
            _first_str([
                "EXIF:DateTimeOriginal",
                "ExifIFD:DateTimeOriginal",
                "DateTimeOriginal",
                "Composite:SubSecDateTimeOriginal",
                "SubSecDateTimeOriginal",
            ]),
            _first_str([
                "EXIF:CreateDate",
                "ExifIFD:CreateDate",
                "CreateDate",
                "Composite:SubSecCreateDate",
                "SubSecCreateDate",
            ]),
            _first_str([
                "XMP-xmp:CreateDate",
                "XMP:CreateDate",
                "CreateDate",
            ]),
            _first_str([
                "EXIF:DateTimeDigitized",
                "DateTimeDigitized",
            ]),
        )
        return src, state

    def read_keywords_many(self, file_paths: list[str]) -> dict[str, KeywordState]:
        if not file_paths:
            return {}

        norm_input = [normalize_path(p) for p in file_paths]
        out: dict[str, KeywordState] = {}

        # Avoid Windows command-line length limits by chunking.
        chunk_size = 200
        for i in range(0, len(norm_input), chunk_size):
            chunk = norm_input[i : i + chunk_size]
            stdout = self._run(
                [
                    "-q",
                    "-q",
                    "-j",
                    "-G1",
                    "-IPTC:Keywords",
                    "-XMP-dc:Subject",
                    "-EXIF:DateTimeOriginal",
                    "-EXIF:CreateDate",
                    "-XMP:CreateDate",
                    "-XMP-xmp:CreateDate",
                    "-EXIF:DateTimeDigitized",
                    "-Composite:SubSecDateTimeOriginal",
                    "-Composite:SubSecCreateDate",
                    *chunk,
                ]
            )
            try:
                data = json.loads(stdout)
            except Exception as e:
                raise ExifToolError("Failed to parse exiftool JSON output") from e
            for rec in data:
                src, state = self._parse_keyword_record(rec)
                if src is not None:
                    out[normalize_path(src)] = state

        return out

    def write_keywords(self, file_paths: list[str], keywords: list[str], keep_backup: bool) -> None:
        kws = dedupe_casefold([k.strip() for k in keywords if k.strip()])
        kws.sort(key=lambda s: s.casefold())
        # Clear both lists, then set explicit values (avoid duplicates).
        args: list[str] = []
        if not keep_backup:
            args.append("-overwrite_original")
        args += ["-P", "-IPTC:Keywords=", "-XMP-dc:Subject="]
        for kw in kws:
            args.append(f"-IPTC:Keywords={kw}")
            args.append(f"-XMP-dc:Subject={kw}")
        args += file_paths
        self._run(args)

    def scan_folder_tags(self, folder: str, recursive: bool) -> set[str]:
        out = self._run(
            [
                "-q",
                "-q",
                "-j",
                "-G1",
                *( ["-r"] if recursive else [] ),
                "-ext",
                "jpg",
                "-ext",
                "jpeg",
                "-IPTC:Keywords",
                "-XMP-dc:Subject",
                folder,
            ]
        )
        try:
            data = json.loads(out)
        except Exception as e:
            raise ExifToolError("Failed to parse exiftool JSON output") from e
        tags: set[str] = set()
        for rec in data:
            iptc = rec.get("IPTC:Keywords", [])
            xmp = rec.get("XMP-dc:Subject", [])
            if isinstance(iptc, str):
                iptc = [iptc]
            if isinstance(xmp, str):
                xmp = [xmp]
            for lst in (iptc, xmp):
                if isinstance(lst, list):
                    for x in lst:
                        if isinstance(x, str) and x.strip():
                            tags.add(x.strip())
        return tags

    def scan_iptc_empty(self, file_paths: list[str]) -> set[str]:
        if not file_paths:
            return set()
        empty: set[str] = set()
        seen: set[str] = set()
        norm_input = [normalize_path(p) for p in file_paths]

        # Avoid Windows command-line length limits by chunking.
        chunk_size = 200
        for i in range(0, len(norm_input), chunk_size):
            chunk = norm_input[i : i + chunk_size]
            out = self._run(["-q", "-q", "-j", "-G1", "-IPTC:Keywords", *chunk])
            try:
                data = json.loads(out)
            except Exception as e:
                raise ExifToolError("Failed to parse exiftool JSON output") from e
            for rec in data:
                src = rec.get("SourceFile")
                if not isinstance(src, str):
                    continue
                src_norm = normalize_path(src)
                seen.add(src_norm)
                iptc = rec.get("IPTC:Keywords", rec.get("Keywords", []))
                if isinstance(iptc, str):
                    iptc = [iptc]
                if not iptc:
                    empty.add(src_norm)

        return empty

    def copy_exif_date_to_xmp(self, file_paths: list[str], keep_backup: bool) -> None:
        if not file_paths:
            return
        args: list[str] = ["-q", "-q", "-P"]
        if not keep_backup:
            args.append("-overwrite_original")
        args.append("-XMP:CreateDate<EXIF:DateTimeOriginal")
        args += file_paths
        self._run(args)
