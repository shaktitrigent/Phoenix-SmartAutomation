"""Migrate recognized old starter artifacts. Dry-run unless --apply is supplied."""
import argparse
import ast
from pathlib import Path
import re
import shutil


def migrate(project, apply=False):
    project = Path(project)
    changes = []
    base = project / "pages/base_page.py"
    if base.exists():
        text = base.read_text(encoding="utf-8")
        updated = re.sub(r'os\.environ\.get\("APP_URL",\s*"[^"\n]*"\)', 'os.environ["APP_URL"]', text)
        if updated != text: changes.append((base, updated))
    starter = project / "tests/login/test_login.py"
    if starter.exists():
        text = starter.read_text(encoding="utf-8")
        if text.startswith('"""Starter login tests for '):
            updated = '\n'.join([
                '"""Generic starter smoke test; add reviewed business tests separately."""',
                'from playwright.sync_api import expect', '',
                'def test_application_page_loads(page, base_url):',
                '    page.goto(base_url, wait_until="domcontentloaded")',
                '    expect(page.locator("body")).to_be_visible()', '',
            ])
            changes.append((starter, updated))
    for path, text in changes:
        ast.parse(text)
        if apply:
            backup = path.with_suffix(path.suffix + ".pre_generic_backup")
            if backup.exists(): raise ValueError("Backup exists; review it before rerunning migration")
            shutil.copy2(path, backup)
            path.write_text(text, encoding="utf-8")
    return [path.relative_to(project).as_posix() for path,_ in changes]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for name in migrate(args.project, args.apply): print(("Updated: " if args.apply else "Would update: ") + name)
