"""Small CPU conversion status records; percentages come from completed work."""
import json
import secrets
import subprocess
import tempfile
import time
from pathlib import Path


def write(path,stage,*,status='running',done=None,total=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    value={'stage':stage,'status':status,'updated_at':time.time(),'percent':None}
    if total and done is not None:value.update(done=done,total=total,percent=round(max(0,min(100,done/total*100)),1))
    temp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
    try:
        temp.write_text(json.dumps(value),encoding='utf-8')
        for attempt in range(8):
            try:temp.replace(path);return True
            except PermissionError:
                # Windows readers and antivirus scanners can briefly deny a
                # replace. Progress is telemetry: it must not abort FFmpeg.
                if attempt==7:return False
                time.sleep(min(.01*2**attempt,.2))
    finally:
        try:temp.unlink(missing_ok=True)
        except PermissionError:pass


def read(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {'status':'waiting','stage':'In attesa della preparazione','percent':None,'updated_at':0}


def ffmpeg(command,path,duration,stage):
    """Read FFmpeg's media timestamps while stderr stays bounded on disk."""
    write(path,stage,done=0,total=duration)
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen([str(command[0]),'-progress','pipe:1','-nostats',*map(str,command[1:])],stdout=subprocess.PIPE,stderr=errors,text=True,encoding='utf-8',errors='replace',creationflags=0x08000000 if __import__('os').name=='nt' else 0)
        last=0
        try:
            for line in process.stdout:
                key,_,value=line.strip().partition('=')
                if key not in ('out_time_us','out_time_ms'):continue
                try:seconds=max(0,int(value)/1_000_000)
                except ValueError:continue
                if time.monotonic()-last>=.25:
                    write(path,stage,done=seconds,total=duration);last=time.monotonic()
            if process.wait():
                errors.seek(0,2);errors.seek(max(0,errors.tell()-1500))
                raise ValueError('Conversione non riuscita: '+errors.read().decode('utf-8','replace'))
        finally:
            if process.poll() is None:process.kill();process.wait()
            process.stdout.close()
