import unittest

from exif_tool import ExifTool


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


if __name__ == "__main__":
    unittest.main()
