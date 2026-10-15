"""Starting RetroArch: the interactive launch used by the UI, and a headless one used to verify
that a game actually loads."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import subprocess
import tempfile
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Settings appended for headless runs: nothing on screen, no audio, no controllers grabbed, and
# never write retroarch.cfg back (so a verification run can't change the user's setup).
HEADLESS_CFG = (
    'video_driver = "null"\naudio_driver = "null"\ninput_joypad_driver = "null"\n'
    'microphone_driver = "null"\nconfig_save_on_exit = "false"\nvideo_fullscreen = "false"\n'
)


class Launcher:
    """One game at a time: launching a new game replaces whatever RetroArch instance we started."""

    def __init__(self, retroarch_exe: Path) -> None:
        self.exe = retroarch_exe
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def launch(self, core: str, content: str) -> None:
        with self._lock:
            self.stop()
            log.info("launching %s with %s", content, Path(core).name)
            self._proc = subprocess.Popen([str(self.exe), "-f", "-L", core, content], cwd=self.exe.parent)
            threading.Thread(target=_bring_to_front, args=(self._proc,), daemon=True).start()

    def stop(self) -> None:
        """Close the game we started (only ours -- never other RetroArch instances)."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


def _bring_to_front(proc: subprocess.Popen, timeout: float = 20.0) -> None:
    """Windows denies focus to windows created by a background process (this server), which would
    leave the game without keyboard/controller input. Wait for RetroArch's window, lift the
    foreground lock with a synthetic Alt tap, then activate it."""
    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def visit(hwnd, _lparam):
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == proc.pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and proc.poll() is None:
        found.clear()
        user32.EnumWindows(visit, 0)
        if found:
            time.sleep(1.0)  # let it finish switching to fullscreen
            VK_MENU, KEYEVENTF_KEYUP, SW_RESTORE = 0x12, 0x2, 9
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            user32.ShowWindow(found[0], SW_RESTORE)
            user32.SetForegroundWindow(found[0])
            return
        time.sleep(0.3)


def headless_log(retroarch_exe: Path, core: str, content: str, frames: int = 300, timeout: float = 60.0) -> str:
    """Run a game invisibly for a few hundred frames and return RetroArch's log."""
    with tempfile.TemporaryDirectory(prefix="gamenight-") as tmp:
        cfg, logfile = Path(tmp) / "headless.cfg", Path(tmp) / "run.log"
        cfg.write_text(HEADLESS_CFG, encoding="ascii")
        proc = subprocess.Popen(
            [str(retroarch_exe), "--verbose", f"--log-file={logfile}", f"--appendconfig={cfg}",
             f"--max-frames={frames}", "-L", core, content],
            cwd=retroarch_exe.parent, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return logfile.read_text(encoding="utf-8", errors="replace") if logfile.exists() else ""
