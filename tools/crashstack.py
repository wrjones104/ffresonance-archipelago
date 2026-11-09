"""Names the UE4SS frames of a crash report with UE4SS.pdb, through dbghelp.

Run: python tools/crashstack.py <crash folder name> [<crash folder name> ...]
The folders are in %LOCALAPPDATA%/FFRS/Saved/Crashes. The game's own frames stay as offsets.
"""
import ctypes, os, re, sys
from ctypes import wintypes as W

UE = r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\ue4ss"
CR = os.path.expandvars(r"%LOCALAPPDATA%\FFRS\Saved\Crashes")
d = ctypes.WinDLL("dbghelp")
k = ctypes.WinDLL("kernel32")
k.GetCurrentProcess.restype = W.HANDLE
h = k.GetCurrentProcess()
d.SymSetOptions(0x2 | 0x10 | 0x40)  # undname, load lines, deferred off is fine
d.SymInitializeW.argtypes = [W.HANDLE, W.LPCWSTR, W.BOOL]
d.SymInitializeW(h, UE, False)
d.SymLoadModuleExW.restype = ctypes.c_uint64
d.SymLoadModuleExW.argtypes = [W.HANDLE, W.HANDLE, W.LPCWSTR, W.LPCWSTR, ctypes.c_uint64, W.DWORD, ctypes.c_void_p, W.DWORD]
BASE = 0x180000000
got = d.SymLoadModuleExW(h, None, UE + r"\UE4SS.dll", None, BASE, 0, None, 0)
print("loaded", hex(got))


class SYM(ctypes.Structure):
    _fields_ = [("SizeOfStruct", W.ULONG), ("TypeIndex", W.ULONG), ("Reserved", ctypes.c_uint64 * 2), ("Index", W.ULONG), ("Size", W.ULONG),
                ("ModBase", ctypes.c_uint64), ("Flags", W.ULONG), ("Value", ctypes.c_uint64), ("Address", ctypes.c_uint64), ("Register", W.ULONG),
                ("Scope", W.ULONG), ("Tag", W.ULONG), ("NameLen", W.ULONG), ("MaxNameLen", W.ULONG), ("Name", ctypes.c_char * 512)]


class LINE(ctypes.Structure):
    _fields_ = [("SizeOfStruct", W.DWORD), ("Key", ctypes.c_void_p), ("LineNumber", W.DWORD), ("FileName", ctypes.c_char_p), ("Address", ctypes.c_uint64)]


d.SymFromAddr.argtypes = [W.HANDLE, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(SYM)]
d.SymGetLineFromAddr64.argtypes = [W.HANDLE, ctypes.c_uint64, ctypes.POINTER(W.DWORD), ctypes.POINTER(LINE)]


def name(off):
    s = SYM(); s.SizeOfStruct = 88; s.MaxNameLen = 500
    disp = ctypes.c_uint64()
    a = BASE + off
    if not d.SymFromAddr(h, a, ctypes.byref(disp), ctypes.byref(s)):
        return "?"
    l = LINE(); l.SizeOfStruct = ctypes.sizeof(LINE)
    d2 = W.DWORD()
    src = ""
    if d.SymGetLineFromAddr64(h, a, ctypes.byref(d2), ctypes.byref(l)):
        src = f"  [{l.FileName.decode().split(chr(92))[-1]}:{l.LineNumber}]"
    return s.Name.decode() + src


for c in sys.argv[1:]:
    raw = open(fr"{CR}\{c}\CrashContext.runtime-xml", "rb").read()
    t = raw.decode("utf-16" if raw[:2] == b"\xff\xfe" else "utf8", "replace")
    st = re.search(r"<PCallStack>(.*?)</PCallStack>", t, re.S).group(1)
    print("=====", c, re.search(r"<ErrorMessage>(.*?)<", t).group(1))
    last = None
    n = 0
    for line in st.splitlines():
        m = re.match(r"\s*(\S+)\s+0x[0-9a-f]+ \+ ([0-9a-f]+)", line)
        if not m:
            continue
        mod, off = m.group(1), int(m.group(2), 16)
        n += 1
        text = name(off) if mod == "UE4SS" else ""
        if text.startswith(("luaV_", "luaD_", "luaH_")) and text == last:
            continue
        print(f"{n:3d} {mod:22s} {off:9x}  {text}"[:170])
        last = text
