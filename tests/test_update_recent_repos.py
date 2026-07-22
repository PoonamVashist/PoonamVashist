from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.update_recent_repos import (
    END_MARKER,
    START_MARKER,
    filter_repositories,
    render_recent_repositories,
    update_readme,
    updated_readme,
)


class RecentRepositoriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "username": "PoonamVashist",
            "limit": 2,
            "sort": "created",
            "direction": "desc",
            "exclude": ["PoonamVashist"],
            "require_description": True,
        }

    def test_filters_profile_repository_forks_archives_and_missing_descriptions(self) -> None:
        repositories = [
            {"name": "PoonamVashist", "description": "Profile"},
            {"name": "forked", "description": "Fork", "fork": True},
            {"name": "archived", "description": "Old", "archived": True},
            {"name": "undocumented", "description": None},
            {"name": "first", "description": "First", "language": "Python"},
            {"name": "second", "description": "Second", "language": "SQL"},
            {"name": "third", "description": "Third"},
        ]

        selected = filter_repositories(repositories, self.config)

        self.assertEqual([repo["name"] for repo in selected], ["first", "second"])

    def test_render_escapes_repository_content(self) -> None:
        rendered = render_recent_repositories(
            [
                {
                    "name": "data<platform>",
                    "html_url": "https://example.com/?a=1&b=2",
                    "description": "Reliable <data> & pipelines",
                    "language": "Python",
                    "pushed_at": "2026-07-22T12:00:00Z",
                }
            ]
        )

        self.assertIn("data&lt;platform&gt;", rendered)
        self.assertIn("a=1&amp;b=2", rendered)
        self.assertIn("Reliable &lt;data&gt; &amp; pipelines", rendered)
        self.assertIn("Updated 2026-07-22", rendered)

    def test_update_is_idempotent(self) -> None:
        initial = f"Before\n{START_MARKER}\nold\n{END_MARKER}\nAfter\n"
        rendered = "<table>\n</table>"

        with tempfile.TemporaryDirectory() as directory:
            readme = Path(directory) / "README.md"
            readme.write_text(initial, encoding="utf-8")

            self.assertTrue(update_readme(readme, rendered))
            self.assertFalse(update_readme(readme, rendered))

    def test_requires_exactly_one_marker_pair(self) -> None:
        with self.assertRaises(ValueError):
            updated_readme("README without markers", "content")


if __name__ == "__main__":
    unittest.main()
