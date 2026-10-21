"""Frame-exact CPU extraction and fitting for timeline post production."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'runtime/tools/documents'
sys.path[:0] = [str(ROOT), str(LIB)]
dll = os.add_dll_directory(str(LIB)) if os.name == 'nt' and LIB.is_dir() else None


def emit(event, **value):
    print(json.dumps({'event': event, **value}, ensure_ascii=False), flush=True)


def process_tree():
    """Stop kills the encoder as well as this worker; no orphan FFmpeg processes."""
    if os.name != 'nt':
        return None
    import ctypes as C
    from ctypes import wintypes as W
    from h3chat.windows_sandbox import EXTENDED_LIMITS
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [C.c_void_p, W.LPCWSTR]; kernel.CreateJobObjectW.restype = W.HANDLE
    kernel.SetInformationJobObject.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]; kernel.SetInformationJobObject.restype = W.BOOL
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]; kernel.AssignProcessToJobObject.restype = W.BOOL
    kernel.CloseHandle.argtypes = [W.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    limits = EXTENDED_LIMITS(); limits.BasicLimitInformation.LimitFlags = 0x2000
    if not handle or not kernel.SetInformationJobObject(handle, 9, C.byref(limits), C.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        error = C.get_last_error()
        if handle: kernel.CloseHandle(handle)
        raise C.WinError(error)
    return handle


def probe(path):
    import av
    with av.open(str(path), options={'protocol_whitelist': 'file'}) as container:
        if not container.streams.video:
            raise ValueError('Il file non contiene una traccia video.')
        video = container.streams.video[0]
        duration = float(video.duration * video.time_base) if video.duration is not None else (container.duration or 0) / av.time_base
        return {'duration': duration, 'width': video.width, 'height': video.height,
                'frames': video.frames, 'fps': float(video.average_rate or 0)}


def render(request):
    source = Path(request['source']); output = Path(request['output'])
    frames = request['frames']; start = request.get('start', 0)
    if type(frames) is not int or not 1 <= frames <= 360 or type(start) not in (int, float) or not math.isfinite(start) or start < 0:
        raise ValueError('Intervallo video non valido.')
    width, height = request['width'], request['height']
    if any(type(n) is not int or n < 2 or n > 16384 or n % 2 for n in (width, height)):
        raise ValueError('Formato video non valido.')
    if output.resolve() == source.resolve():
        raise ValueError('La sostituzione deve creare un nuovo file.')
    duration = frames / 24
    info = probe(source)
    if info['duration'] + 1 / 24 + 1e-6 < start + duration:
        raise ValueError(f"Il video è troppo corto: servono {duration:.3f} s dalla posizione {start:.3f}. Non rallento né ripeto i fotogrammi.")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix('.pending.mp4')
    filters = f'fps=24,scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=0.083333333'
    command = [str(ROOT / 'runtime/remix/ffmpeg.exe'), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(start), '-protocol_whitelist', 'file,pipe', '-i', str(source)]
    audio = request.get('audio')
    if audio:
        command += ['-ss', str(request.get('audio_start', 0)), '-protocol_whitelist', 'file,pipe', '-i', str(audio)]
    command += ['-map', '0:v:0', '-vf', filters, '-r', '24', '-fps_mode', 'cfr', '-enc_time_base', '1:24', '-frames:v', str(frames), '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-threads', '4']
    if audio:
        command += ['-map', '1:a:0', '-af', f'apad,atrim=duration={duration},asetpts=N/SR/TB', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2']
    else:
        command += ['-an']
    command += ['-t', str(duration), '-movflags', '+faststart', str(partial)]
    emit('stage', message='Timeline · export dello spezzone' if audio else 'Timeline · adattamento della sostituzione')
    try:
        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT, creationflags=0x08000000 if os.name == 'nt' else 0)
        if process.returncode:
            raise ValueError('Rendering dello spezzone non riuscito: ' + process.stderr[-1500:])
        result = probe(partial)
        if result['frames'] != frames or abs(result['fps'] - 24) > 1e-6 or (result['width'], result['height']) != (width, height):
            raise ValueError('Il risultato non conserva fotogrammi e formato richiesti: ' + json.dumps(result))
        partial.replace(output)
        return result | {'path': str(output)}
    finally:
        partial.unlink(missing_ok=True)


if __name__ == '__main__':
    emit('hello')
    try:
        worker_job = process_tree()
        emit('result', result=render(json.loads(sys.stdin.readline())))
    except Exception as error:
        emit('error', message=str(error))
