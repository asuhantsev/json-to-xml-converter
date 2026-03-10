#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsontoxml import convert_json_to_xml_file


def make_large_input(base_source: Path, out_path: Path, multiplier: int):
    data = json.loads(base_source.read_text(encoding="utf-8"))
    messages = data.get("messages", [])
    data["messages"] = messages * multiplier
    out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Benchmark conversion on enlarged Telegram export")
    parser.add_argument("--source", default="exports/ChatExport_2024-12-27/result.json")
    parser.add_argument("--multiplier", type=int, default=20)
    parser.add_argument("--workdir", default="exports")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    large_json = workdir / f"benchmark_input_x{args.multiplier}.json"
    large_xml = workdir / f"benchmark_output_x{args.multiplier}.xml"

    make_large_input(Path(args.source), large_json, args.multiplier)

    start = time.perf_counter()
    result = convert_json_to_xml_file(
        source_path=str(large_json),
        output_path=str(large_xml),
        use_date_range=False,
        include_reactions=True,
        human_readable=False,
    )
    elapsed = time.perf_counter() - start

    size_mb = large_xml.stat().st_size / (1024 * 1024)
    print(f"messages={result['messages']}")
    print(f"elapsed_sec={elapsed:.3f}")
    print(f"throughput_msgs_per_sec={result['messages'] / elapsed:.1f}")
    print(f"output_mb={size_mb:.2f}")
    print(f"input_file={large_json}")
    print(f"output_file={large_xml}")


if __name__ == "__main__":
    main()
