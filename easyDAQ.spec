# -*- mode: python -*-
import sys
sys.setrecursionlimit(5000)
block_cipher = None


a = Analysis(['easyDAQ.py'],
             pathex=['C:\\Users\\alexh\\OneDrive\\Documents\\3_DesignTeams\\masa\\all-things-engine-controller\\engine_controller\\gui\\easyDAQ'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='easyDAQ',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True , icon='C:\\Users\\alexh\\OneDrive\\Documents\\3_DesignTeams\\masa\\all-things-engine-controller\\engine_controller\\gui\\easyDAQ\\logos\\logo_ed.ico')
