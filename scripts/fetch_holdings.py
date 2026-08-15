import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from angelone.api.holdings import HoldingsAPI


def main():
    print("Fetching mutual fund holdings...")

    data = HoldingsAPI().get_holdings()

    print()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()