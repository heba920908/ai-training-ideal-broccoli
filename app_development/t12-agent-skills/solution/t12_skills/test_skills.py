import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from t12_skills.custom.models import load_skills

ROOT = Path(__file__).parent
PACKAGES = [ROOT / "_skills", ROOT / "custom" / "_skills"]


def test_all_skill_packages_are_complete_and_references_resolve():
    skills = [skill for directory in PACKAGES for skill in load_skills(directory)]
    assert {skill.name for skill in skills} == {"calculator", "style-guide", "unit-converter"}
    for skill in skills:
        text = (skill.skill_dir / "SKILL.md").read_text()
        assert "TODO" not in text
        assert len(skill.description) > 40
        for target in re.findall(r"\]\(([^)]+)\)", text):
            assert (skill.skill_dir / target).is_file(), target
    converter = next(skill for skill in skills if skill.name == "unit-converter")
    assert converter.license == "Apache-2.0"
    assert converter.allowed_tools == ["execute_code"]
    assert converter.metadata["author"] == "ai-powered-apps-development-expert"


@pytest.mark.parametrize(
    "frontmatter",
    [
        "[unterminated",
        "- a\n- b",
        "42",
        "name: null\ndescription: null",
        "name: bad--name\ndescription: description",
        "name: UPPER\ndescription: description",
        "name: different\ndescription: description",
        "name: sample\ndescription: ' '",
        "name: sample\ndescription: 123",
        "name: sample\ndescription: description\nmetadata: [bad]",
        "name: sample\ndescription: description\nallowed-tools: [42]",
    ],
)
def test_invalid_metadata_is_skipped_without_raw_content(tmp_path, capsys, frontmatter):
    skill = tmp_path / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_text(f"---\n{frontmatter}\n---\nprivate-body")
    assert load_skills(tmp_path) == []
    diagnostic = capsys.readouterr().out
    assert "WARN" in diagnostic
    assert "private-body" not in diagnostic


def test_valid_metadata_remains_metadata_only(tmp_path):
    directory = tmp_path / "sample"
    directory.mkdir()
    (directory / "SKILL.md").write_text(
        "---\nname: sample\ndescription: Use for a sample.\n"
        "metadata:\n  version: '1.0'\nallowed-tools: execute_code\n---\nprivate-body"
    )
    skill = load_skills(tmp_path)[0]
    assert skill.description == "Use for a sample."
    assert "private-body" not in str(skill)


def test_style_inventory_and_minimum_assigned_examples():
    directory = ROOT / "_skills" / "style-guide"
    reference = (directory / "REFERENCE.md").read_text()
    examples = (directory / "EXAMPLES.md").read_text()
    for section in [
        "Emails",
        "Blog Posts",
        "Social Media",
        "Support / Help Content",
        "Grammar & Mechanics",
    ]:
        assert section in reference
    for section, minimum in [
        ("Email Subject Lines", 4),
        ("Blog Heading Rewrites", 4),
        ("Common Jargon", 8),
    ]:
        body = examples.split(f"## {section}", 1)[1].split("\n## ", 1)[0]
        assert len([line for line in body.splitlines() if line.startswith("| ")]) >= minimum + 2
    for text in (reference, examples, (directory / "SKILL.md").read_text()):
        assert "TODO" not in text
    assert examples.count("**Before:**") >= 4
    assert examples.count("**After:**") >= 4
    assert examples.count("**Changes:**") >= 4


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("2^10", 1024),
        ("(144 * 3) + sqrt(256) - 2^8", 192),
        ("sin(pi / 2) + cos(0)", 2),
        ("2^10 + sqrt(144)", 1036),
    ],
)
def test_calculator_course_samples_use_real_script(expression, expected):
    result = subprocess.run(
        [sys.executable, str(ROOT / "_skills/calculator/scripts/calculate.py"), expression],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert float(result.stdout.split("Result:")[1]) == pytest.approx(expected)


@pytest.mark.parametrize(
    "value,source,target,expected,category",
    [
        (98.6, "fahrenheit", "celsius", 37, "temperature"),
        (98.6, "fahrenheit", "kelvin", 310.15, "temperature"),
        (1.5, "tb", "mb", 1572864, "data"),
        (127, "km/h", "mph", 78.91414141414141, "speed"),
        (127, "km/h", "knots", 68.57457354157507, "speed"),
        (577, "acres", "ha", 233.503822, "area"),
        (577, "acres", "m2", 2335038.22, "area"),
        (3, "cups", "ml", 709.764, "volume"),
    ],
)
def test_converter_course_samples_use_real_script(value, source, target, expected, category):
    script = ROOT / "custom/_skills/unit-converter/scripts/convert.py"
    code = (
        "import json, runpy; "
        f"convert = runpy.run_path({str(script)!r})['convert_units']; "
        f"print(json.dumps(convert({value!r}, {source!r}, {target!r})))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10, check=True
    )
    number, actual_category = json.loads(result.stdout)
    assert number == pytest.approx(expected, rel=1e-8, abs=1e-8)
    assert actual_category == category


def test_frontmatter_is_mapping_not_placeholder():
    for path in [*ROOT.glob("_skills/*/SKILL.md"), *ROOT.glob("custom/_skills/*/SKILL.md")]:
        metadata = yaml.safe_load(path.read_text().split("---", 2)[1])
        assert isinstance(metadata, dict)
        assert metadata["name"] == path.parent.name
