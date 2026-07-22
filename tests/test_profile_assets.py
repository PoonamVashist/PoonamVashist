from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEADERS = [
    ROOT / "assets" / "profile-header-light.svg",
    ROOT / "assets" / "profile-header-dark.svg",
]
ICONS = [
    "databricks.svg",
    "python.svg",
    "sql.svg",
    "apachespark.svg",
    "delta-lake.svg",
    "azure.svg",
    "apacheairflow.svg",
    "snowflake.svg",
    "aws.svg",
]


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class ProfileAssetTests(unittest.TestCase):
    def test_headers_are_accessible_animated_svg_files(self) -> None:
        for path in HEADERS:
            with self.subTest(path=path.name):
                root = ET.parse(path).getroot()
                names = [local_name(element.tag) for element in root.iter()]

                self.assertEqual(root.attrib.get("viewBox"), "0 0 1000 320")
                self.assertIn("title", names)
                self.assertIn("desc", names)
                self.assertIn("animateMotion", names)
                self.assertNotIn("script", names)

    def test_every_readme_icon_exists_and_is_valid_svg(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for filename in ICONS:
            with self.subTest(filename=filename):
                path = ROOT / "assets" / "icons" / filename
                self.assertTrue(path.is_file())
                root = ET.parse(path).getroot()
                self.assertEqual(local_name(root.tag), "svg")
                self.assertIn(f"./assets/icons/{filename}", readme)

    def test_readme_has_light_and_dark_header_sources(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("./assets/profile-header-light.svg", readme)
        self.assertIn("./assets/profile-header-dark.svg", readme)
        self.assertIn('media="(prefers-color-scheme: dark)"', readme)


if __name__ == "__main__":
    unittest.main()
