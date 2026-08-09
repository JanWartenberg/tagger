import unittest
from unittest.mock import patch

from exif_tool import ExifTool
from services.keyword_limits import IptcKeywordLengthError


class ExifToolDateParsingTests(unittest.TestCase):
    def test_reads_exififd_capture_date_from_grouped_exiftool_json(self) -> None:
        _source, state = ExifTool()._parse_keyword_record(
            {
                "SourceFile": r"D:\Fotos\2006_10 Aschaffenburg\IMG_0369.jpg",
                "IFD0:ModifyDate": "2006:10:01 08:44:39",
                "ExifIFD:DateTimeOriginal": "2006:10:01 08:44:39",
                "ExifIFD:CreateDate": "2006:10:01 08:44:39",
                "XMP-xmp:CreateDate": "2006:10:01 08:44:39",
            }
        )

        self.assertEqual(state.date_original, "2006:10:01 08:44:39")
        self.assertEqual(state.date_create, "2006:10:01 08:44:39")
        self.assertEqual(state.date_display, "2006:10:01 08:44:39")

    def test_marks_a_field_error_as_unreadable_without_confusing_missing_tags(
        self,
    ) -> None:
        _source, state = ExifTool()._parse_keyword_record(
            {
                "SourceFile": "photo.jpg",
                "IPTC:Keywords": [],
                "Error": "IPTC:Keywords could not be read",
            }
        )

        self.assertFalse(state.iptc_readable)
        self.assertTrue(state.xmp_readable)

    def test_writes_each_keyword_field_explicitly_in_one_operation(self) -> None:
        exif = ExifTool()
        with patch.object(exif, "_run") as run:
            exif.write_keyword_fields(
                ["photo.jpg"], [" IPTC "], ["XMP"], keep_backup=False
            )

        self.assertEqual(
            run.call_args.args[0],
            [
                "-overwrite_original",
                "-P",
                "-IPTC:Keywords=",
                "-XMP-dc:Subject=",
                "-IPTC:Keywords=IPTC",
                "-XMP-dc:Subject=XMP",
                "photo.jpg",
            ],
        )

    def test_rejects_an_over_limit_iptc_keyword_before_running_exiftool(self) -> None:
        exif = ExifTool()
        with patch.object(exif, "_run") as run:
            with self.assertRaises(IptcKeywordLengthError) as error:
                exif.write_keyword_fields(
                    ["photo.jpg"], ["x" * 65], ["x" * 65], keep_backup=False
                )

        self.assertEqual(error.exception.violation.utf8_byte_count, 65)
        run.assert_not_called()

    def test_allows_an_over_limit_xmp_only_keyword(self) -> None:
        exif = ExifTool()
        with patch.object(exif, "_run") as run:
            exif.write_keyword_fields(["photo.jpg"], [], ["x" * 65], keep_backup=False)

        self.assertIn("-XMP-dc:Subject=" + "x" * 65, run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
