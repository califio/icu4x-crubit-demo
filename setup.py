#!/usr/bin/env python3
"""Fetch pinned dependencies and build Crubit's Cargo driver."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
PINS = json.loads((ROOT / "dependencies.json").read_text())

def run(*args, **kwargs):
    print("+ " + " ".join(str(arg) for arg in args), flush=True)
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)

def git_output(directory, *args):
    return subprocess.check_output(["git", "-C", str(directory), *args], text=True).strip()

def checkout(name, deps):
    pin = PINS[name]
    target = deps / name
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix=name + "-", dir=deps) as tmp:
            stage = Path(tmp) / "repo"
            run("git", "init", "--quiet", stage)
            run("git", "-C", stage, "remote", "add", "origin", pin["url"])
            run("git", "-C", stage, "fetch", "--depth=1", "--filter=blob:none", "origin", pin["commit"])
            if pin.get("sparse_paths"):
                run("git", "-C", stage, "sparse-checkout", "set", "--cone", *pin["sparse_paths"])
            run("git", "-C", stage, "checkout", "--quiet", "--detach", "FETCH_HEAD")
            stage.rename(target)
    if git_output(target, "rev-parse", "HEAD") != pin["commit"]:
        raise RuntimeError(f"{target} is not at the pinned commit")
    if git_output(target, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError(f"{target} has tracked changes; use a clean checkout")
    return target

def fetch_icu4c(deps):
    pin = PINS["icu4c"]
    target = deps / "icu4c"
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix="icu4c-", dir=deps) as tmp:
            stage = Path(tmp)
            archive = stage / "source.tgz"
            digest = hashlib.sha256()
            request = urllib.request.Request(pin["url"], headers={"User-Agent": "icu-collation-demo"})
            print("Downloading " + pin["url"], flush=True)
            with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != pin["sha256"]:
                raise RuntimeError("ICU4C source archive checksum mismatch")
            with tarfile.open(archive) as source:
                for member in source.getmembers():
                    path = Path(member.name)
                    if path.is_absolute() or ".." in path.parts or path.parts[0] != "icu" or not (member.isfile() or member.isdir()):
                        raise RuntimeError("Unexpected archive entry: " + member.name)
                source.extractall(stage)
            (stage / "icu").rename(target)
    locid = target / "source/common/locid.cpp"
    if hashlib.sha256(locid.read_bytes()).hexdigest() != pin["locid_sha256"]:
        raise RuntimeError("The ICU4C source does not match the vulnerable release")
    return target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps-dir", type=Path, default=ROOT / "third_party")
    parser.add_argument("--toolchain", default=PINS["rust"]["toolchain"], help="Override the local name of the same pinned Rust compiler")
    parser.add_argument("--sources-only", action="store_true", help="Fetch sources without installing or building Rust tools")
    args = parser.parse_args()
    deps = args.deps_dir.resolve()
    deps.mkdir(parents=True, exist_ok=True)
    fetch_icu4c(deps)
    repos = {name: checkout(name, deps) for name in ("crubit", "corrosion")}
    if args.sources_only:
        return
    compiler = subprocess.run(["rustup", "run", args.toolchain, "rustc", "-Vv"],
                              capture_output=True, text=True)
    expected_commit = "commit-hash: " + PINS["rust"]["commit"]
    if compiler.returncode or expected_commit not in compiler.stdout:
        if args.toolchain != PINS["rust"]["toolchain"]:
            raise RuntimeError("The selected local toolchain is not the pinned Rust compiler")
        run("rustup", "toolchain", "install", args.toolchain, "--profile", "minimal",
            "--component", "rustc-dev", "--component", "llvm-tools", "--component", "rustfmt")
    else:
        installed = subprocess.check_output(["rustup", "component", "list", "--installed",
                                             "--toolchain", args.toolchain], text=True)
        for component in ("rustc-dev", "llvm-tools", "rustfmt"):
            if not any(line.startswith(component + "-") or line == component for line in installed.splitlines()):
                run("rustup", "component", "add", "--toolchain", args.toolchain, component)
    version = subprocess.check_output(["rustup", "run", args.toolchain, "rustc", "-Vv"], text=True)
    if expected_commit not in version:
        raise RuntimeError("Crubit requires the pinned Rust compiler; the selected toolchain differs")
    run("cargo", "+" + args.toolchain, "build", "--release", "--locked",
        "--manifest-path", repos["crubit"] / "Cargo.toml", "-p", "cargo-cpp_api_from_rust")
    run("cargo", "+" + args.toolchain, "fetch", "--locked", "--manifest-path", ROOT / "rust/Cargo.toml")

if __name__ == "__main__":
    main()
