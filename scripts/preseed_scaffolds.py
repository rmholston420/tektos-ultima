#!/usr/bin/env python3
"""
Pre-seed common Terminal-Bench 2.1 task scaffolds.

Downloads and extracts common dependencies that Tektos agents need
for hard tasks, so they don't waste turns downloading them.
"""

import os
import subprocess
import sys
from pathlib import Path

def run(cmd, cwd=None, timeout=120):
    """Run a shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def main():
    base = Path("/home/rmholston/dev/tektos-ultima-v1")
    print("=" * 60)
    print("Pre-seeding Terminal-Bench 2.1 scaffolds")
    print("=" * 60)

    # 1. Check if doomgeneric is already available
    doom_path = Path("/app/doomgeneric")
    if doom_path.exists():
        print(f"\n[SKIP] /app/doomgeneric already exists")
    else:
        print(f"\n[1/3] Checking for doomgeneric source...")
        # Try to find it in common locations
        for candidate in [
            "/home/rmholston/dev/doomgeneric",
            "/tmp/doomgeneric",
            "/home/rmholston/doomgeneric",
        ]:
            if Path(candidate).exists():
                print(f"  Found at {candidate}")
                break
        else:
            print(f"  Not found — agent will need to download it")

    # 2. Check if povray source is available
    povray_path = Path("/app/povray-2.2")
    if povray_path.exists():
        print(f"\n[SKIP] /app/povray-2.2 already exists")
    else:
        print(f"\n[2/3] Checking for POV-Ray 2.2 source...")
        # Try to download from Internet Archive
        archive_url = "https://archive.org/download/povray-2.2/povray-2.2-src.tar.gz"
        print(f"  Downloading from {archive_url}...")
        success, output = run(f"curl -sL --max-time 60 -o /tmp/povray-2.2-src.tar.gz '{archive_url}'")
        if success and Path("/tmp/povray-2.2-src.tar.gz").exists():
            size = Path("/tmp/povray-2.2-src.tar.gz").stat().st_size
            print(f"  Downloaded {size} bytes")
            # Extract
            success2, output2 = run("tar xzf /tmp/povray-2.2-src.tar.gz -C /app/ 2>/dev/null || true")
            if success2:
                print(f"  Extracted to /app/")
            else:
                print(f"  Extraction failed: {output2[:200]}")
        else:
            print(f"  Download failed: {output[:200]}")

    # 3. Check build tools
    print(f"\n[3/3] Checking build tools...")
    tools = ["gcc", "g++", "make", "cmake", "python3", "node", "npm"]
    for tool in tools:
        success, _ = run(f"which {tool}")
        status = "✓" if success else "✗"
        print(f"  {status} {tool}")

    # 4. Check cross-compiler for MIPS
    print(f"\n  Checking MIPS cross-compiler...")
    success, _ = run("which mips-linux-gnu-gcc")
    status = "✓" if success else "✗"
    print(f"  {status} mips-linux-gnu-gcc")
    if not success:
        print(f"    Agent will need to install it: apt-get install gcc-mips-linux-gnu")

    print(f"\n{'='*60}")
    print("Pre-seeding complete")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
