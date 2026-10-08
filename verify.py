#!/usr/bin/env python3
"""Check contact sorting and the CVE input against both native executables."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent

def run(build, backend, *args, stdin=""):
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:abort_on_error=0:symbolize=1")
    return subprocess.run([str(build / backend), *args], input=stdin, capture_output=True,
                          text=True, errors="replace", env=env, timeout=20)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    build = args.build_dir.resolve()
    names = ["Zimmermann", "Müller", "Andersson", "Özil", "Mueller", "Meyer", "", "a\tb"]
    for locale in ("de", "de_DE", "de@collation=phonebook", "sv", "en-US"):
        results = [run(build, backend, "--locale", locale, "--", *names)
                   for backend in ("icu4c-demo", "icu4x-demo")]
        assert all(p.returncode == 0 for p in results), [(p.returncode, p.stderr) for p in results]
        rows = [p.stdout.splitlines() for p in results]
        assert rows[0] == rows[1], (locale, rows)
        assert sorted(rows[0]) == sorted(names), (locale, rows[0])
    for backend in ("icu4c-demo", "icu4x-demo"):
        piped = run(build, backend, "--locale", "de", "--stdin", stdin="Zimmermann\nAndersson\n")
        assert piped.returncode == 0 and piped.stdout == "Andersson\nZimmermann\n", piped
    vulnerable = run(build, "icu4c-demo", "--cve")
    safe = run(build, "icu4x-demo", "--cve")
    assert vulnerable.returncode != 0 and "AddressSanitizer: heap-use-after-free" in vulnerable.stderr, vulnerable.stderr
    assert safe.returncode == 0 and "Müller" in safe.stdout and "Zimmermann" in safe.stdout, (safe.stdout, safe.stderr)
    print("PASS: ordinary sorting agrees; ICU4C reports the use-after-free; ICU4X completes")

if __name__ == "__main__":
    main()
