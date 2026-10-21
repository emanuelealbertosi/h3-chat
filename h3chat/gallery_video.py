"""Small gallery summaries of existing timelines. No imports, decoders or models."""
import json
import re
import threading
from collections import OrderedDict
from pathlib import Path
from .downloads import safe_join


class VideoSummaries:
    def __init__(self,root):
        self.root=root;self.cache=OrderedDict();self.lock=threading.Lock()

    def describe(self,path,generation=None):
        parts=Path(path).parts
        if len(parts)<3 or parts[0]!='outputs' or not re.fullmatch('[a-f0-9]{32}',parts[1]):return {}
        ident=parts[1]
        try:
            target=safe_join(self.root,f'outputs/{ident}/scenes.json')
            stat=target.stat();signature=(stat.st_mtime_ns,stat.st_size)
            with self.lock:
                cached=self.cache.get(ident)
                if cached and cached[0]==signature:
                    self.cache.move_to_end(ident);summary=cached[1]
                else:summary=None
            if summary is None:
                # Only metadata, once per checkpoint revision, shared by its clips.
                if stat.st_size>32*1024*1024:return {}
                record=json.loads(target.read_text(encoding='utf-8'))
                timeline=record.get('timeline')
                count=len(timeline) if isinstance(timeline,list) else 0
                summary={'count':count,'ready':count>0 and record.get('completed')==count,
                    'clip_only':record.get('revision_remount') is False and not record.get('working_timeline'),'modified':stat.st_mtime}
                with self.lock:
                    self.cache[ident]=(signature,summary);self.cache.move_to_end(ident)
                    while len(self.cache)>128:self.cache.popitem(last=False)
            if not summary['ready']:return {}
            clip=bool((generation or {}).get('clip_only')) or bool(re.fullmatch(r'clip-\d+\.mp4',parts[-1]))
            # Scene intermediates are not full movies, even inside a timeline job.
            if len(parts)!=3:return {}
            if summary['clip_only'] and not clip:return {}
            return {'video_kind':'clip' if clip else 'timeline','timeline_id':ident,
                'clip_count':summary['count'],'modified':summary['modified']}
        except (OSError,ValueError,TypeError,AttributeError,PermissionError):return {}
