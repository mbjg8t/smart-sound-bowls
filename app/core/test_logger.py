import json
from datetime import datetime
from pathlib import Path


LOG_DIR = Path("data/test_results")
LOG_FILE = LOG_DIR / "bowl_tests.jsonl"


def save_test(
    test_type,
    mount_position,
    settings,
    results,
):
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().astimezone()

    record = {
        "timestamp":
            timestamp.isoformat(
                timespec="seconds"
            ),

        "test_type":
            str(test_type),

        "mount_position":
            str(
                mount_position or
                "Unlabeled position"
            ),

        "settings":
            settings,

        "results":
            results,
    }

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(
                record,
                separators=(",", ":"),
            )
        )

        f.write("\n")

    return record


def load_tests():
    if not LOG_FILE.exists():
        return []

    records = []

    with LOG_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                records.append(
                    json.loads(line)
                )

            except json.JSONDecodeError:
                continue

    return records


def summarize_tests():
    records = load_tests()

    summary = []

    for index, record in enumerate(
        records,
        start=1,
    ):
        results = record.get(
            "results",
            {},
        )

        settings = record.get(
            "settings",
            {},
        )

        summary.append({
            "id": index,

            "timestamp":
                record.get(
                    "timestamp"
                ),

            "test_type":
                record.get(
                    "test_type"
                ),

            "mount_position":
                record.get(
                    "mount_position"
                ),

            "frequency_hz":
                results.get(
                    "center_frequency_hz",
                    results.get(
                        "frequency_hz",
                        settings.get(
                            "frequency"
                        ),
                    ),
                ),

            "drive_percent":
                results.get(
                    "peak_drive_percent",
                    settings.get(
                        "peak_drive_percent"
                    ),
                ),

            "peak_response_g":
                results.get(
                    "peak_response_g"
                ),

            "max_abs_g":
                results.get(
                    "max_abs_g"
                ),

            "invalid_samples":
                results.get(
                    "invalid_samples"
                ),

            "preset":
                results.get(
                    "preset",
                    settings.get(
                        "preset"
                    ),
                ),
        })

    return summary
