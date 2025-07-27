#!/usr/bin/env python3
#
# Checks out ET:Legacy below this git checkout in order to test if
# ET:Legacy compiles fine with ET:Legacy lib PRs.
import os
import shutil
import subprocess
import sys

from pathlib import Path


def run(cmd, capture_output=False, **kwargs):
    print(f"+ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    result = subprocess.run(
        cmd, check=True, text=True, capture_output=capture_output, **kwargs
    )
    if capture_output:
        return result.stdout.strip()
    return None


def remove_submodule(path: Path, name: str):
    print(f"Removing submodule '{name}' from {path}...")

    gitmodules = path / ".gitmodules"
    modified_gitmodules = False

    # Try to remove from .gitmodules using git config
    if gitmodules.exists():
        try:
            run(["git", "config", "-f", str(gitmodules), "--remove-section", f"submodule.{name}"], cwd=path)
            modified_gitmodules = True
        except subprocess.CalledProcessError:
            print(f"Warning: submodule.{name} not found in .gitmodules — attempting manual removal")
            # Fallback: manually remove the section
            content = gitmodules.read_text()
            lines = content.splitlines()
            new_lines = []
            skip = False
            for line in lines:
                if line.strip().startswith(f"[submodule \"{name}\"]"):
                    skip = True
                    continue
                if skip and line.strip().startswith("["):
                    skip = False
                if not skip:
                    new_lines.append(line)
            new_content = "\n".join(new_lines) + "\n"
            gitmodules.write_text(new_content)
            modified_gitmodules = True

    # Stage .gitmodules to allow git rm
    if modified_gitmodules:
        try:
            run(["git", "add", ".gitmodules"], cwd=path)
        except subprocess.CalledProcessError:
            print("Warning: could not stage .gitmodules")

    # Remove from .git/config
    try:
        run(["git", "config", "--remove-section", f"submodule.{name}"], cwd=path)
    except subprocess.CalledProcessError:
        print(f"Warning: submodule.{name} not found in .git/config")

    # De-index the submodule path
    try:
        run(["git", "rm", "--cached", "-f", name], cwd=path)
    except subprocess.CalledProcessError:
        print(f"Warning: could not unstage '{name}' (maybe not tracked?)")

    # Delete submodule directory
    submodule_path = path / name
    if submodule_path.exists():
        shutil.rmtree(submodule_path, ignore_errors=True)

    # Remove leftover submodule git metadata
    modules_dir = path / ".git" / "modules" / name
    if modules_dir.exists():
        shutil.rmtree(modules_dir, ignore_errors=True)


def copy_local_repo_to_libs(src_root: Path, dst_libs: Path, exclude_dir: str):
    print(f"Copying local repository into '{dst_libs}'...")
    dst_libs.mkdir(parents=True, exist_ok=True)

    for item in src_root.iterdir():
        # if item.name == exclude_dir or item.name == ".git":
        if item.name == exclude_dir:
            continue
        target = dst_libs / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True)
        else:
            shutil.copy2(item, target)


def main():
    root = Path.cwd()
    ci_tmp = root / "ci-tmp"
    ci_tmp_bk = root / "ci-tmp-bk"
    repo_url = "https://github.com/etlegacy/etlegacy.git"

    # Clone or copy ci-tmp
    if not ci_tmp.exists():
        if ci_tmp_bk.exists():
            print("Copying ci-tmp-bk to ci-tmp...")
            shutil.copytree(ci_tmp_bk, ci_tmp)
        else:
            print("Cloning repository...")
            run(["git", "clone", repo_url, str(ci_tmp)])

    # Remove 'libs' submodule
    remove_submodule(ci_tmp, "libs")

    # Re-initialize remaining submodules
    print("Initializing and updating remaining submodules...")
    run(["git", "submodule", "sync"], cwd=ci_tmp)
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=ci_tmp)

    # Copy local repo into ./ci-tmp/libs/
    dst_libs = ci_tmp / "libs"
    copy_local_repo_to_libs(root, dst_libs, exclude_dir="ci-tmp")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
