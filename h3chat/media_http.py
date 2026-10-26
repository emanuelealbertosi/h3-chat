"""Stream generated audio with byte ranges, so the player can seek without buffering it all."""
import re
import mimetypes

def send_audio(handler,path,*,attachment=False):
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
 handler.send_header('Content-Type',{'.wav':'audio/wav','.mkv':'video/x-matroska','.mov':'video/quicktime','.m4a':'audio/mp4'}.get(path.suffix.lower(),mimetypes.guess_type(path.name)[0] or 'application/octet-stream'))
 handler.send_header('Content-Security-Policy',"default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri 'none'")
 handler.send_header('Referrer-Policy','no-referrer')
 if attachment or path.suffix.lower() in ('.html','.svg','.js','.mjs','.xml') or not mimetypes.guess_type(path.name)[0]:handler.send_header('Content-Disposition','attachment')
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
