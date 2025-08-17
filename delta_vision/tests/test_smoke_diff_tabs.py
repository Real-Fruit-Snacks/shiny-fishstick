import os
import sys
import tempfile

import pytest

from delta_vision.entry_points import main as entry_main

HEADER = '20250101 "echo hello"\n'


def write_tmp(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix='.txt')
    os.close(fd)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


@pytest.mark.asyncio
async def test_diff_viewer_tabs_activation(monkeypatch):
    # Create two NEW files with same command to produce multiple tabs
    write_tmp(HEADER + 'line A\n')
    new2 = write_tmp(HEADER + 'line B\n')
    # Create an OLD file to enable the OLD tab
    old = write_tmp(HEADER + 'old line\n')

    created = {}

    def fake_run(self):
        created['app'] = self

    from textual.app import App

    monkeypatch.setattr(App, 'run', fake_run, raising=True)

    # Launch app; neutralize argparse interaction with pytest
    monkeypatch.setattr(sys, 'argv', ['prog'])
    entry_main()
    app = created.get('app')
    assert app is not None

    # Push diff screen directly to avoid scanning folders
    from delta_vision.screens.diff_viewer import SideBySideDiffScreen

    app.push_screen(SideBySideDiffScreen(new_path=new2, old_path=old))

    async with app.run_test() as pilot:
        await pilot.press('l')
        await pilot.press('h')
        assert app.screen is not None
        await pilot.press('q')
        assert app.screen is not None
