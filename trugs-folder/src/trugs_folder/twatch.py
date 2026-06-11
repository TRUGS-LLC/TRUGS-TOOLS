# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""twatch - Monitor folder.trug.json and auto-regenerate docs on change.

Watches for changes to folder.trug.json and triggers re-rendering
of AAA.md, README.md, and ARCHITECTURE.md.

<trl>
PROCESS twatch SHALL MONITOR FILE folder_trug_json AND SHALL EMIT DATA rendered_docs ON CHANGE.
</trl>
"""

import time
from pathlib import Path
from typing import Callable, Dict, Optional, Union

from trugs_folder.utils import TRUG_FILENAME, load_graph
from trugs_folder.renderer import render_all


# AGENT claude SHALL DEFINE FUNCTION twatch.
def twatch(
    directory: Union[str, Path],
    interval: float = 1.0,
    callback: Optional[Callable[[Dict[str, str]], None]] = None,
    once: bool = False,
) -> Dict[str, str]:
    """Watch folder.trug.json and regenerate docs on change.

    Uses polling to detect file changes (no external dependencies).

    Args:
        directory: Directory containing folder.trug.json
        interval: Polling interval in seconds
        callback: Optional callback called with render results on each change
        once: If True, check once and return (useful for testing)

    Returns:
        Last render results (dict of filename -> content)

    Raises:
        FileNotFoundError: If folder.trug.json doesn't exist

    <trl>
    FUNCTION twatch SHALL SCAN FILE folder_trug_json THEN RENDER DATA docs AND WRITE FILE rendered_output SUBJECT_TO CHANGE detected.
    </trl>
    """
    dirpath = Path(directory).resolve()
    trug_path = dirpath / TRUG_FILENAME

    if not trug_path.exists():
        raise FileNotFoundError(f"No {TRUG_FILENAME} found in {dirpath}")

    last_mtime = 0.0
    last_results: Dict[str, str] = {}

    while True:
        try:
            current_mtime = trug_path.stat().st_mtime
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                trug = load_graph(dirpath)
                results = render_all(trug)

                # Write rendered files
                for filename, content in results.items():
                    filepath = dirpath / filename
                    filepath.write_text(content, encoding="utf-8")

                last_results = results

                if callback:
                    callback(results)

            if once:
                return last_results

            time.sleep(interval)

        except KeyboardInterrupt:
            break
        except Exception:
            if once:
                raise
            time.sleep(interval)

    return last_results
