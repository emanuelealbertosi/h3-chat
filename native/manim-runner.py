"""Trusted entrypoint inside the AppContainer; scene code has no broker handles."""
import json
import os
from pathlib import Path
import runpy
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'runtime/tools/lab'),str(ROOT/'native/vendor')]
if os.name=='nt':
    dll=os.add_dll_directory(str(ROOT/'runtime/tools/lab'))
    # AppContainer denies DOS volume-name lookup through MountPointManager.
    # VOLUME_NAME_NT keeps full OS canonicalization and reparse resolution.
    # AppContainer cannot query the DOS MountPointManager; the trusted broker
    # supplies a drive/device map without granting any additional filesystem ACL.
    import ctypes as C
    from ctypes import wintypes as W
    import ntpath
    k=C.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
    k.GetFinalPathNameByHandleW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD];k.GetFinalPathNameByHandleW.restype=W.DWORD
    k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
    original_path=ntpath._getfinalpathname
    def canonical_path(path):
        try:return original_path(path)
        except PermissionError:
            handle=k.CreateFileW(path,0,7,None,3,0x02000000,None)
            if handle==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
            try:
                buffer=C.create_unicode_buffer(32768);length=k.GetFinalPathNameByHandleW(handle,buffer,len(buffer),2)
                if not length or length>=len(buffer):raise C.WinError(C.get_last_error())
                devices=json.loads(os.environ['H3_DRIVE_MAP'])
                for drive,device in devices.items():
                    if buffer.value.casefold().startswith(device.casefold()+'\\'):
                        return '\\\\?\\'+drive+buffer.value[len(device):]
                raise ValueError('Volume canonico non riconosciuto.')
            finally:k.CloseHandle(handle)
    ntpath._getfinalpathname=canonical_path

def main():
    folder=Path.cwd();request=json.loads((folder/'request.json').read_text(encoding='utf-8'))
    # Some Windows hosts deny the NUL device inside AppContainer. Redirect child
    # process output to a disposable job file, without widening device access.
    os.devnull = str(folder / 'process-null.log')
    Path(os.devnull).touch()
    from manim import Scene,tempconfig
    opts=request['options']
    # TeX runs without shell escape and sees only copied assets / job caches.
    os.environ.update(TEXMFOUTPUT=str(folder/'tex'),TEXMFVAR=str(folder/'cache/texmf'),
        TEXMFCONFIG=str(folder/'cache/texmf-config'),MPLCONFIGDIR=str(folder/'cache/matplotlib'),
        TEXMFCACHE=str(folder/'cache/texmf'),shell_escape='f',openin_any='p',openout_any='p')
    from manim.utils import tex_file_writing
    original=tex_file_writing.make_tex_compilation_command
    def tex_command(*args,**kwargs):
        command=original(*args,**kwargs);command.insert(1,'-no-shell-escape');return command
    tex_file_writing.make_tex_compilation_command=tex_command
    with tempconfig({'media_dir':str(folder/'media'),'output_file':'animation','pixel_width':opts['width'],
            'pixel_height':opts['height'],'frame_rate':opts['fps'],'renderer':'opengl' if opts['device']=='gpu' else 'cairo',
            'background_color':'#12352f','disable_caching':True,'write_to_movie':True,'verbosity':'WARNING'}):
        namespace=runpy.run_path(str(folder/'scene.py'),run_name='__h3_manim__')
        cls=namespace.get(request['scene_name'])
        if not isinstance(cls,type) or not issubclass(cls,Scene):raise ValueError('La classe selezionata deve derivare da Scene o ThreeDScene.')
        scene=cls();scene.render()
        path=Path(scene.renderer.file_writer.movie_file_path).resolve()
        if not path.is_relative_to(folder):raise ValueError('Il video deve restare nella cartella del rendering.')
        (folder/'result.json').write_text(json.dumps({'path':str(path)}),encoding='utf-8')

if __name__=='__main__':
    try:main()
    except Exception:
        traceback.print_exc();sys.exit(1)
