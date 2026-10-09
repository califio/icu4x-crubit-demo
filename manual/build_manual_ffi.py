#!/usr/bin/env python3
"""Build the manual bridge against the Rust artifacts already used by Crubit."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--toolchain", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    projects = list((args.build_dir / "cargo").rglob("locale_collator_cc_api.rs"))
    if len(projects) != 1:
        raise RuntimeError("Expected one generated Crubit project; use a clean Release build")
    artifacts = projects[0].parent / "target/release"
    adapters = list(artifacts.rglob("liblocale_collator-*.rlib"))
    if len(adapters) != 1:
        raise RuntimeError("Expected one compiled Rust adapter; use a clean Release build")
    adapter = adapters[0]
    dependencies = {path.parent for pattern in ("*.rlib", "*.so", "*.dylib")
                    for path in artifacts.rglob(pattern)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("manual_ffi.rs")
    command = ["rustc", "+" + args.toolchain, "--edition=2024",
               "--crate-name=benchmark_manual_ffi", "--crate-type=staticlib",
               "-C", "opt-level=3", "--extern", "locale_collator=" + str(adapter)]
    if adapter.with_suffix(".rmeta").exists():
        command += ["--extern", "locale_collator=" + str(adapter.with_suffix(".rmeta"))]
    for path in sorted(dependencies):
        command += ["-L", "dependency=" + str(path)]
    command += [str(source), "-o", str(args.output)]
    subprocess.run(command, check=True)
    metadata = {"toolchain": args.toolchain,
                "adapter_rlib_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
                "manual_ffi_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("Built manual FFI against Crubit's compiled Rust adapter.")


if __name__ == "__main__":
    main()
