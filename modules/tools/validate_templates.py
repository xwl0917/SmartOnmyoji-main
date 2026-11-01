# -*- coding: utf-8 -*-
"""
Validate template folders against their img_pos.json.

Checks:
  - img_pos.json is valid JSON and a list of objects;
  - every entry has a non-empty name and a known flag;
  - duplicate names are reported (conflicting flags are errors);
  - real_pos / click_pos shapes are valid;
  - flagged entries (start / stop / mark) must have a matching image;
  - images without a JSON entry and stale JSON entries are reported as warnings.

Usage:
    python modules/tools/validate_templates.py
    python modules/tools/validate_templates.py --strict
    python modules/tools/validate_templates.py img/yuhun img/tupo
    python modules/tools/validate_templates.py --root C:\\path\\to\\project

Exit code:
    1 when there are errors, or when --strict is used and there are warnings;
    0 otherwise.
"""

import argparse
import json
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VALID_FLAGS = {"", "start", "skip", "mark", "stop"}
FLAGGED_REQUIRING_IMAGE = {"start", "stop", "mark"}


def is_point(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(number, (int, float)) for number in value)
    )


def is_point_list(value):
    return isinstance(value, (list, tuple)) and all(is_point(point) for point in value)


def collect_images(folder):
    images = {}
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            images.setdefault(path.stem, path)
    return images


def validate_folder(folder, strict=False):
    """Return (errors, warnings) for one template folder."""
    errors = []
    warnings = []
    json_path = folder / "img_pos.json"
    images = collect_images(folder)

    if not json_path.is_file():
        warnings.append("no img_pos.json; coordinates/flags are disabled in this folder")
        return errors, warnings

    try:
        with json_path.open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
    except (OSError, ValueError) as error:
        errors.append(f"cannot parse img_pos.json: {error}")
        return errors, warnings

    if not isinstance(entries, list):
        errors.append("img_pos.json root must be a list")
        return errors, warnings

    seen = {}
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"entry #{index} is not an object")
            continue

        name = entry.get("name")
        flag = entry.get("flag", "")
        if not isinstance(name, str) or not name:
            errors.append(f"entry #{index} has no valid name")
            continue
        if not isinstance(flag, str) or flag not in VALID_FLAGS:
            errors.append(f"{name}: invalid flag {flag!r}")
            flag = ""

        if name in seen:
            if seen[name] != flag:
                errors.append(
                    f"{name}: duplicate entry with conflicting flags "
                    f"({seen[name]!r} vs {flag!r})"
                )
            else:
                warnings.append(f"{name}: duplicate entry with the same flag")
        else:
            seen[name] = flag

        real_pos = entry.get("real_pos", [])
        click_pos = entry.get("click_pos", [])
        if real_pos and not is_point(real_pos):
            errors.append(f"{name}: real_pos must be [] or [x, y]")
        if click_pos and not is_point_list(click_pos):
            errors.append(f"{name}: click_pos must be [] or a list of [x, y]")
        if click_pos and not real_pos:
            warnings.append(f"{name}: click_pos is set but real_pos is empty")

        if name not in images:
            if flag in FLAGGED_REQUIRING_IMAGE:
                errors.append(f"{name}: flag {flag!r} requires an image, but none exists")
            else:
                warnings.append(f"{name}: JSON entry has no matching image")

    for name in sorted(set(images) - set(seen)):
        warnings.append(f"{name}: image has no JSON entry (flag/click position disabled)")

    return errors, warnings


def find_template_folders(root):
    img_root = root / "img"
    if not img_root.is_dir():
        return []
    folders = []
    for path in sorted(img_root.iterdir()):
        if path.is_dir() and any(
            child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS
            for child in path.iterdir()
        ):
            folders.append(path)
    return folders


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate img_pos.json template data.")
    parser.add_argument("folders", nargs="*", help="template folders (default: img/*)")
    parser.add_argument("--root", default=None, help="project root (default: auto-detect)")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    if args.folders:
        folders = [Path(item).resolve() for item in args.folders]
    else:
        folders = find_template_folders(root)

    if not folders:
        print("No template folders found under:", root / "img")
        return 1

    total_errors = 0
    total_warnings = 0
    for folder in folders:
        errors, warnings = validate_folder(folder, strict=args.strict)
        total_errors += len(errors)
        total_warnings += len(warnings)
        try:
            display = folder.relative_to(root)
        except ValueError:
            display = folder
        image_count = len(collect_images(folder))
        print(f"== {display}  ({image_count} images)")
        for message in errors:
            print("  [ERROR]", message)
        for message in warnings:
            print("  [WARN ]", message)
        if not errors and not warnings:
            print("  OK")

    print()
    print(f"Summary: {len(folders)} folders, {total_errors} errors, {total_warnings} warnings")
    if total_errors:
        print("Template validation failed.")
        return 1
    if args.strict and total_warnings:
        print("Template validation failed (--strict: warnings are errors).")
        return 1
    print("Template validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
