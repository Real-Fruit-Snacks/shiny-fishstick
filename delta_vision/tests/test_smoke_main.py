import os
import tempfile

import pytest
from textual.app import App

from delta_vision.screens.main_screen import MainScreen


@pytest.mark.asyncio
async def test_main_screen_navigation_pilot():
    # Setup temp dirs and a minimal keywords file
    with tempfile.TemporaryDirectory() as new_dir, tempfile.TemporaryDirectory() as old_dir:
        # Create keywords file separately to avoid Windows delete-lock issues
        fd, kw_path = tempfile.mkstemp(text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as kwf:
            kwf.write("# Test (magenta)\nfoo\n")

        # Create very small test files with header and a couple of lines
        def make_file(folder, name, date="20250101", cmd="echo x", lines=None):
            if lines is None:
                lines = ["alpha", "beta"]
            fp = os.path.join(folder, name)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(f"{date} \"{cmd}\"\n")
                f.write("\n".join(lines))
            return fp

        make_file(new_dir, "a.txt")
        make_file(old_dir, "a.txt")

        class TestApp(App):
            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        try:
            async with TestApp().run_test() as pilot:
                # We start on MainScreen; open Stream with '1'
                await pilot.press("1")
                # Stream screen should mount; try j/k/G/gg
                await pilot.press("j", "k", "G", "g", "g")
                # Go back
                await pilot.press("q")

                # Open Search with '2' and perform a basic search
                await pilot.press("2")
                await pilot.pause()
                await pilot.press("enter")  # empty search no-op
                # Toggle regex and back
                await pilot.press("r")
                await pilot.press("q")

                # Open Compare with '4'
                await pilot.press("4")
                # Press Enter to open the selected pair in Diff viewer
                await pilot.press("enter")
                # Try tab cycling and toggle highlights
                await pilot.press("l", "h", "K")
                # Back to Compare, then back to Home
                await pilot.press("q")
                await pilot.press("q")
        finally:
            try:
                os.unlink(kw_path)
            except Exception:
                pass
