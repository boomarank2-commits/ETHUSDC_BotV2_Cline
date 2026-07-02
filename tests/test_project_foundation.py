from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_required_project_files_exist():
    required_files = [
        ".clineignore",
        ".gitignore",
        "README.md",
        "requirements.txt",
        "pyproject.toml",
        "docs/GPT_CONTINUATION_GUIDE_20260701.md",
        "docs/IMPLEMENTATION_PLAN.md",
        "docs/ARENA_AI_REQUEST_AFTER_WINDOW_SELECTION_EDGE_20260702.md",
        "memory-bank/projectbrief.md",
        "memory-bank/productContext.md",
        "memory-bank/activeContext.md",
        "memory-bank/systemPatterns.md",
        "memory-bank/techContext.md",
        "memory-bank/progress.md",
        "memory-bank/openQuestions.md",
        ".clinerules/01-working-mode.md",
        ".clinerules/02-no-assumptions.md",
        ".clinerules/03-bot-truth.md",
        ".clinerules/04-token-discipline.md",
        ".clinerules/05-testing-and-handoff.md",
    ]

    missing = [file for file in required_files if not (PROJECT_ROOT / file).exists()]

    assert missing == []


def test_single_truth_docs_contain_core_rules():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (
        PROJECT_ROOT / "docs" / "GPT_CONTINUATION_GUIDE_20260701.md"
    ).read_text(encoding="utf-8")
    implementation_plan = (
        PROJECT_ROOT / "docs" / "IMPLEMENTATION_PLAN.md"
    ).read_text(encoding="utf-8")

    assert "ETHUSDC" in readme
    assert "USDC" in readme
    assert "LONG-only" in readme
    assert "Kein Short" in readme
    assert "Futures" in readme
    assert "Margin" in readme
    assert "Leverage" in readme

    assert "730 Tagen Training" in readme
    assert "365-Tage-Blindtest" in readme
    assert "Blindtest-Lernen" in readme

    assert "activity_first_router" in guide
    assert "Smoke und Full muessen denselben Pfad verwenden" in guide
    assert "Keine UI/Router-Integration von BRH-v1" in implementation_plan


def test_archive_is_not_truth():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Alte verstreute Truth-/Arena-/Patch-Dateien wurden entfernt" in readme
