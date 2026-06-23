from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.context_data_ensure import ensure_all_context_data_ready


if __name__ == "__main__":
    results = ensure_all_context_data_ready()
    for result in results:
        print(result, flush=True)