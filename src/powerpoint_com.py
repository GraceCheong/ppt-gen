import sys

PP_WINDOW_MINIMIZED = 2


def _try_setattr(target, name, value):
    try:
        setattr(target, name, value)
        return True
    except Exception:
        return False


def quit_powerpoint(powerpoint):
    """Call Quit() and, on Windows, forcibly kill any surviving POWERPNT.EXE process.

    powerpoint.Quit() is a fire-and-forget COM call that sometimes leaves the
    process alive (e.g. when a dialog is pending or Quit itself raises).
    Killing the process by PID ensures no zombie instances accumulate between
    requests, which is the primary cause of E_OUTOFMEMORY on subsequent calls.
    """
    pid = None
    if sys.platform == "win32":
        try:
            pid = powerpoint.ProcessID
        except Exception:
            pass

    try:
        powerpoint.Quit()
    except Exception:
        pass

    if pid and sys.platform == "win32":
        try:
            import subprocess
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass


def minimize_powerpoint_window(powerpoint):
    _try_setattr(powerpoint, "WindowState", PP_WINDOW_MINIMIZED)
    try:
        active_window = powerpoint.ActiveWindow
    except Exception:
        return
    _try_setattr(active_window, "WindowState", PP_WINDOW_MINIMIZED)


def create_powerpoint_application(comtypes_client):
    powerpoint = comtypes_client.CreateObject("PowerPoint.Application")
    _try_setattr(powerpoint, "DisplayAlerts", 0)

    # Some PowerPoint versions reject Visible=0 for automation.
    # In that case, keep document windows hidden and minimize the app shell.
    if not _try_setattr(powerpoint, "Visible", 0):
        _try_setattr(powerpoint, "Visible", 1)
        minimize_powerpoint_window(powerpoint)

    return powerpoint


def open_presentation_hidden(powerpoint, pptx_path, read_only=True):
    presentation = powerpoint.Presentations.Open(
        pptx_path,
        ReadOnly=-1 if read_only else 0,
        WithWindow=0,
    )
    minimize_powerpoint_window(powerpoint)
    return presentation
