"""
Regression tests for corrupt-state resilience.

A skill file or bug-pattern file can be left truncated by an interrupted write,
a full disk, or a crash mid-save. Before these fixes a single unreadable file
raised JSONDecodeError straight out of SkillLibrary.list() / BugLibrary.__init__,
which took out /skills, GET /api/skills, autonomous skill capture, and — because
BugLibrary is constructed during startup — agent construction itself.

The contract asserted here: corrupt entries are skipped, valid entries survive,
and nothing raises.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class CorruptSkillLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vortex_resil_")
        self._prev = os.environ.get("VORTEX_HOME")
        os.environ["VORTEX_HOME"] = self.tmp
        self.skills_dir = Path(self.tmp) / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("VORTEX_HOME", None)
        else:
            os.environ["VORTEX_HOME"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, raw):
        (self.skills_dir / f"{name}.json").write_text(raw)

    def _lib(self):
        from skills import SkillLibrary
        return SkillLibrary()

    def _good(self, name="good"):
        self._write(name, json.dumps(
            {"name": name, "description": "a valid skill", "steps": ["step one"]}
        ))

    def test_empty_file_is_skipped(self):
        self._write("empty", "")
        self.assertEqual(self._lib().list(), [])

    def test_truncated_json_is_skipped(self):
        self._write("trunc", '{"name": "half"')
        self.assertEqual(self._lib().list(), [])

    def test_non_json_garbage_is_skipped(self):
        self._write("junk", "not json at all")
        self.assertEqual(self._lib().list(), [])

    def test_valid_json_of_wrong_shape_is_skipped(self):
        # a JSON array is parseable but is not a skill record
        self._write("notdict", "[1, 2, 3]")
        self.assertEqual(self._lib().list(), [])

    def test_good_skills_survive_alongside_corrupt_ones(self):
        self._good("alpha")
        self._good("beta")
        self._write("empty", "")
        self._write("trunc", '{"name":')
        self._write("junk", "%%%")
        names = sorted(s["name"] for s in self._lib().list())
        self.assertEqual(names, ["alpha", "beta"])

    def test_get_returns_none_for_corrupt_skill(self):
        self._write("broken", "{{{")
        self.assertIsNone(self._lib().get("broken"))

    def test_get_still_returns_valid_skill(self):
        self._good("usable")
        self.assertEqual(self._lib().get("usable")["name"], "usable")

    def test_get_missing_skill_returns_none(self):
        self.assertIsNone(self._lib().get("does_not_exist"))

    def test_list_does_not_raise_on_all_corrupt_library(self):
        for i in range(5):
            self._write(f"bad{i}", "definitely not json")
        try:
            self._lib().list()
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"list() raised on an all-corrupt library: {exc!r}")


class CorruptBugLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vortex_resil_bug_")
        self._prev = os.environ.get("VORTEX_HOME")
        os.environ["VORTEX_HOME"] = self.tmp

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("VORTEX_HOME", None)
        else:
            os.environ["VORTEX_HOME"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, raw):
        (Path(self.tmp) / "bug_patterns.json").write_text(raw)

    def _lib(self):
        from skills import BugLibrary
        return BugLibrary()

    def test_truncated_bug_file_yields_empty_patterns(self):
        self._write("{")
        self.assertEqual(self._lib().patterns, [])

    def test_empty_bug_file_yields_empty_patterns(self):
        self._write("")
        self.assertEqual(self._lib().patterns, [])

    def test_wrong_shape_bug_file_yields_empty_patterns(self):
        self._write('{"not": "a list"}')
        self.assertEqual(self._lib().patterns, [])

    def test_valid_bug_patterns_still_load(self):
        self._write(json.dumps([{"error": "boom", "fix": "do not boom"}]))
        self.assertEqual(len(self._lib().patterns), 1)

    def test_recovers_by_overwriting_corrupt_file(self):
        self._write("garbage")
        lib = self._lib()
        lib.add({"error": "timeout", "fix": "retry"})
        self.assertEqual(len(self._lib().patterns), 1)


if __name__ == "__main__":
    unittest.main()
