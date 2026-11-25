"""All ctypes bindings for the Win32 APIs we use.

Every function gets explicit argtypes/restype. Handles are pointer-sized; leaving
them as the default C int truncates them on 64-bit and causes random crashes.
"""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    shcore = ctypes.WinDLL("shcore", use_last_error=True)
except OSError:  # very old Windows
    shcore = None

get_last_error = ctypes.get_last_error

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

# ---------------------------------------------------------------- constants
ERROR_ALREADY_EXISTS = 183

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RETURN = 0x0D
VK_SPACE = 0x20
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_V = 0x56

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2
KEYEVENTF_KEYUP = 0x0002

MAPVK_VK_TO_VSC = 0

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

MONITOR_DEFAULTTONEAREST = 2
GA_ROOT = 2

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
PROCESS_PER_MONITOR_DPI_AWARE = 2


# ---------------------------------------------------------------- structures
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def _fn(dll, name, restype, *argtypes):
    f = getattr(dll, name)
    f.restype = restype
    f.argtypes = list(argtypes)
    return f


# ---------------------------------------------------------------- kernel32
CreateMutexW = _fn(kernel32, "CreateMutexW", wintypes.HANDLE,
                   wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
CloseHandle = _fn(kernel32, "CloseHandle", wintypes.BOOL, wintypes.HANDLE)
GetCurrentThreadId = _fn(kernel32, "GetCurrentThreadId", wintypes.DWORD)
GetCurrentProcessId = _fn(kernel32, "GetCurrentProcessId", wintypes.DWORD)
OpenProcess = _fn(kernel32, "OpenProcess", wintypes.HANDLE,
                  wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
QueryFullProcessImageNameW = _fn(kernel32, "QueryFullProcessImageNameW", wintypes.BOOL,
                                 wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                 ctypes.POINTER(wintypes.DWORD))
try:  # Windows 8+; tells us whether we run inside an MSIX package (Store build)
    GetCurrentPackageFamilyName = _fn(kernel32, "GetCurrentPackageFamilyName", ctypes.c_long,
                                      ctypes.POINTER(ctypes.c_uint32), wintypes.LPWSTR)
except AttributeError:
    GetCurrentPackageFamilyName = None
GlobalAlloc = _fn(kernel32, "GlobalAlloc", wintypes.HGLOBAL, wintypes.UINT, ctypes.c_size_t)
GlobalLock = _fn(kernel32, "GlobalLock", wintypes.LPVOID, wintypes.HGLOBAL)
GlobalUnlock = _fn(kernel32, "GlobalUnlock", wintypes.BOOL, wintypes.HGLOBAL)
GlobalFree = _fn(kernel32, "GlobalFree", wintypes.HGLOBAL, wintypes.HGLOBAL)

# ---------------------------------------------------------------- user32
RegisterHotKey = _fn(user32, "RegisterHotKey", wintypes.BOOL,
                     wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
UnregisterHotKey = _fn(user32, "UnregisterHotKey", wintypes.BOOL, wintypes.HWND, ctypes.c_int)
GetMessageW = _fn(user32, "GetMessageW", wintypes.BOOL,
                  ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
PeekMessageW = _fn(user32, "PeekMessageW", wintypes.BOOL,
                   ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                   wintypes.UINT, wintypes.UINT)
PostThreadMessageW = _fn(user32, "PostThreadMessageW", wintypes.BOOL,
                         wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

GetForegroundWindow = _fn(user32, "GetForegroundWindow", wintypes.HWND)
SetForegroundWindow = _fn(user32, "SetForegroundWindow", wintypes.BOOL, wintypes.HWND)
BringWindowToTop = _fn(user32, "BringWindowToTop", wintypes.BOOL, wintypes.HWND)
IsWindow = _fn(user32, "IsWindow", wintypes.BOOL, wintypes.HWND)
GetAncestor = _fn(user32, "GetAncestor", wintypes.HWND, wintypes.HWND, wintypes.UINT)
GetWindowTextLengthW = _fn(user32, "GetWindowTextLengthW", ctypes.c_int, wintypes.HWND)
GetWindowTextW = _fn(user32, "GetWindowTextW", ctypes.c_int,
                     wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
GetClassNameW = _fn(user32, "GetClassNameW", ctypes.c_int,
                    wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
GetWindowThreadProcessId =_fn(user32, "GetWindowThreadProcessId", wintypes.DWORD,
                               wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
AttachThreadInput = _fn(user32, "AttachThreadInput", wintypes.BOOL,
                        wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)

GetCursorPos = _fn(user32, "GetCursorPos", wintypes.BOOL, ctypes.POINTER(wintypes.POINT))
MonitorFromPoint = _fn(user32, "MonitorFromPoint", wintypes.HMONITOR,
                       wintypes.POINT, wintypes.DWORD)
GetMonitorInfoW = _fn(user32, "GetMonitorInfoW", wintypes.BOOL,
                      wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))

SendInput = _fn(user32, "SendInput", wintypes.UINT,
                wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
MapVirtualKeyW = _fn(user32, "MapVirtualKeyW", wintypes.UINT, wintypes.UINT, wintypes.UINT)
GetAsyncKeyState = _fn(user32, "GetAsyncKeyState", wintypes.SHORT, ctypes.c_int)

OpenClipboard = _fn(user32, "OpenClipboard", wintypes.BOOL, wintypes.HWND)
CloseClipboard = _fn(user32, "CloseClipboard", wintypes.BOOL)
EmptyClipboard = _fn(user32, "EmptyClipboard", wintypes.BOOL)
GetClipboardData = _fn(user32, "GetClipboardData", wintypes.HANDLE, wintypes.UINT)
SetClipboardData = _fn(user32, "SetClipboardData", wintypes.HANDLE,
                       wintypes.UINT, wintypes.HANDLE)
IsClipboardFormatAvailable = _fn(user32, "IsClipboardFormatAvailable", wintypes.BOOL,
                                 wintypes.UINT)
RegisterClipboardFormatW = _fn(user32, "RegisterClipboardFormatW", wintypes.UINT,
                               wintypes.LPCWSTR)
GetClipboardSequenceNumber = _fn(user32, "GetClipboardSequenceNumber", wintypes.DWORD)

try:
    dwmapi = ctypes.WinDLL("dwmapi")
    DwmSetWindowAttribute = _fn(dwmapi, "DwmSetWindowAttribute", ctypes.c_long,
                                wintypes.HWND, wintypes.DWORD, wintypes.LPCVOID, wintypes.DWORD)
except (OSError, AttributeError):
    DwmSetWindowAttribute = None

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWA_BORDER_COLOR = 34

SetProcessDPIAware = _fn(user32, "SetProcessDPIAware", wintypes.BOOL)
try:
    SetProcessDpiAwarenessContext = _fn(user32, "SetProcessDpiAwarenessContext",
                                        wintypes.BOOL, wintypes.HANDLE)
except AttributeError:  # before Windows 10 1703
    SetProcessDpiAwarenessContext = None
if shcore is not None:
    SetProcessDpiAwareness = _fn(shcore, "SetProcessDpiAwareness", ctypes.HRESULT, ctypes.c_int)
else:
    SetProcessDpiAwareness = None


# ---------------------------------------------------------------- helpers
def window_title(hwnd):
    n = GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def package_family_name():
    """MSIX package family name if running packaged (Store build), else None."""
    if not GetCurrentPackageFamilyName:
        return None
    n = ctypes.c_uint32(0)
    GetCurrentPackageFamilyName(ctypes.byref(n), None)  # 15700 = not packaged
    if n.value == 0:
        return None
    buf = ctypes.create_unicode_buffer(n.value)
    if GetCurrentPackageFamilyName(ctypes.byref(n), buf) != 0:
        return None
    return buf.value


def window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_pid(hwnd):
    pid = wintypes.DWORD(0)
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_thread(hwnd):
    return GetWindowThreadProcessId(hwnd, None)


def process_name(pid):
    """Basename of the process executable, e.g. 'slack.exe'; '' if unknown."""
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ""
        return buf.value.rsplit("\\", 1)[-1]
    finally:
        CloseHandle(h)


def cursor_pos():
    pt = wintypes.POINT()
    GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def work_area_at(x, y):
    """(left, top, right, bottom) of the work area of the monitor containing (x, y)."""
    mon = MonitorFromPoint(wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not mon or not GetMonitorInfoW(mon, ctypes.byref(mi)):
        return None
    r = mi.rcWork
    return r.left, r.top, r.right, r.bottom


def key_input(vk, up=False):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki = KEYBDINPUT(vk, MapVirtualKeyW(vk, MAPVK_VK_TO_VSC),
                        KEYEVENTF_KEYUP if up else 0, 0, 0)
    return inp


def send_keys(events):
    """events: list of (vk, up) pairs, sent in a single SendInput call."""
    arr = (INPUT * len(events))(*[key_input(vk, up) for vk, up in events])
    return SendInput(len(events), arr, ctypes.sizeof(INPUT))


def is_down(vk):
    return bool(GetAsyncKeyState(vk) & 0x8000)


def force_foreground(hwnd):
    """SetForegroundWindow with the AttachThreadInput workaround for the foreground lock."""
    if not hwnd or not IsWindow(hwnd):
        return False
    if GetForegroundWindow() == hwnd:
        return True
    if SetForegroundWindow(hwnd) and GetForegroundWindow() == hwnd:
        return True
    me = GetCurrentThreadId()
    fg = GetForegroundWindow()
    fg_tid = window_thread(fg) if fg else 0
    attached = bool(fg_tid and fg_tid != me and AttachThreadInput(me, fg_tid, True))
    try:
        BringWindowToTop(hwnd)
        SetForegroundWindow(hwnd)
    finally:
        if attached:
            AttachThreadInput(me, fg_tid, False)
    return GetForegroundWindow() == hwnd


def style_popup(hwnd, border_rgb):
    """Windows 11: rounded corners + colored hairline border. No-op on older Windows."""
    if not DwmSetWindowAttribute:
        return False
    r, g, b = border_rgb
    ok = True
    for attr, value in ((DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND),
                        (DWMWA_BORDER_COLOR, r | (g << 8) | (b << 16))):
        v = wintypes.DWORD(value)
        ok &= DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0
    return ok


def dark_titlebar(hwnd):
    """Dark title bar for a normal window (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)."""
    if not DwmSetWindowAttribute:
        return False
    v = wintypes.BOOL(True)
    return DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), ctypes.sizeof(v)) == 0


def root_hwnd(child_hwnd):
    return GetAncestor(child_hwnd, GA_ROOT) or child_hwnd
