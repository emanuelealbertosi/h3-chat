"""Stream generated audio with byte ranges, so the player can seek without buffering it all."""
import re

def send_audio(handler,path):
 size=path.stat().st_size;start=0;end=size-1;partial=False
 requested=handler.headers.get('Range')
 if requested:
  match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
  try:
   if not match or not any(match.groups()):raise ValueError()
   if match[1]:
    start=int(match[1]);end=min(int(match[2]),size-1) if match[2] else size-1
   else:
    count=int(match[2])
    if count<=0:raise ValueError()
    start=max(0,size-count)
   if start>=size or start>end:raise ValueError()
  except ValueError:
   handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}');handler.send_header('Content-Length','0');handler.end_headers();return
  partial=True
 handler.send_response(206 if partial else 200)
 handler.send_header('Content-Type','audio/wav')
 handler.send_header('Accept-Ranges','bytes')
 handler.send_header('Content-Length',str(end-start+1))
 handler.send_header('X-Content-Type-Options','nosniff')
 if partial:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
 handler.end_headers()
 with path.open('rb') as stream:
  stream.seek(start);remaining=end-start+1
  while remaining>0:
   chunk=stream.read(min(65536,remaining))
   if not chunk:break
   handler.wfile.write(chunk);remaining-=len(chunk)
