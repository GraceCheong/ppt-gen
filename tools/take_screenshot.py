"""앱 창 영역을 mss로 스크린샷 저장."""
import sys, time, win32gui, ctypes, mss, mss.tools

title_part = sys.argv[1] if len(sys.argv) > 1 else "PO,RR by a tempo"
out = sys.argv[2] if len(sys.argv) > 2 else "C:/dev/ppt-gen/tools/ui_screenshot.png"

hwnd = None
def _cb(h, _):
    global hwnd
    if title_part in win32gui.GetWindowText(h):
        hwnd = h

for _ in range(20):
    win32gui.EnumWindows(_cb, None)
    if hwnd:
        break
    time.sleep(0.5)

if not hwnd:
    print("Window not found:", title_part)
    sys.exit(1)

placement = win32gui.GetWindowPlacement(hwnd)
if placement[1] == 2:
    win32gui.ShowWindow(hwnd, 9)

try:
    ctypes.windll.user32.SetForegroundWindow(hwnd)
except Exception:
    pass
time.sleep(0.5)

left, top, right, bottom = win32gui.GetWindowRect(hwnd)
monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}
with mss.mss() as sct:
    img = sct.grab(monitor)
    mss.tools.to_png(img.rgb, img.size, output=out)
print(f"Saved {img.size[0]}x{img.size[1]} → {out}")
