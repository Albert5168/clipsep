# PyInstaller spec: builds dist/ClipSep/ClipSep.exe (one folder, faster start than one-file)
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = [], [], []
for pkg in ("rapidocr", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h
datas += collect_data_files("opencc")
datas += collect_data_files("pptx")
datas += [("../assets", "assets")]

a = Analysis(["../main.py"], pathex=[".."], datas=datas, binaries=binaries,
             hiddenimports=hiddenimports, excludes=["tkinter", "matplotlib", "torch"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ClipSep", console=False,
          icon="../assets/app.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="ClipSep")
