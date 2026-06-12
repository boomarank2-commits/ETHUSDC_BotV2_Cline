from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_required_project_files_exist():
    required_files = [
        ".clineignore",
        ".gitignore",
        "README.md",
        "requirements.txt",
        "pyproject.toml",
        "docs/MASTER_TRUTH.md",
        "docs/BACKTEST_TRUTH.md",
        "docs/ROUTER_TRUTH.md",
        "docs/DATA_TRUTH.md",
        "docs/UI_TRUTH.md",
        "docs/IMPLEMENTATION_PLAN.md",
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


def test_master_truth_contains_core_rules():
    master_truth = (PROJECT_ROOT / "docs" / "MASTER_TRUTH.md").read_text(encoding="utf-8")
    backtest_truth = (PROJECT_ROOT / "docs" / "BACKTEST_TRUTH.md").read_text(encoding="utf-8")
    router_truth = (PROJECT_ROOT / "docs" / "ROUTER_TRUTH.md").read_text(encoding="utf-8")

    assert "ETHUSDC" in master_truth
    assert "USDC" in master_truth
    assert "LONG only" in master_truth
    assert "No short" in master_truth
    assert "No futures" in master_truth
    assert "No margin" in master_truth
    assert "No leverage" in master_truth

    assert "730 days training" in backtest_truth
    assert "365 days blindtest" in backtest_truth
    assert "no early stop" in backtest_truth.lower()
    assert "negative calculated results must remain visible" in backtest_truth.lower()

    assert "Situation -> Cluster -> Router -> Setup -> Trade" in router_truth


def test_archive_is_not_truth():
    master_truth = (PROJECT_ROOT / "docs" / "MASTER_TRUTH.md").read_text(encoding="utf-8")
    assert "Old READMEs, old reports, old code and old bot folders are not truth." in master_truth
