from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .config import load_addon_options


def main() -> None:
    options_path = Path(os.environ.get("YUNHAI_OPTIONS_PATH", "/data/options.json"))
    config = load_addon_options(options_path)
    print(
        json.dumps(
            {
                "event": "yunhai_intercom_started",
                "config": config.as_dict(),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
