"""CPU-only synthetic round trip through the actual infographic renderer and timeline."""
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'runtime/tools/documents')]
import tempfile
tempfile.tempdir=str(ROOT/'work/clip-tools-test-tmp')
import av
import test_video_clip_worker as media_fixture
import test_video_clip_tools as timeline_fixture
from h3chat.video_clip_tools import request,prepare_infographic,use_infographic
from h3chat.video_resume import checkpoint,save
from h3chat.infographics import build
from h3chat.video_edit import describe


def main():
    assets=media_fixture.ClipWorkerTests();assets.setUp()
    fixture=timeline_fixture.ClipToolTests();fixture.setUp()
    try:
        app=fixture.app;chat,original,refs,outputs,*_=fixture.original()
        import shutil
        shutil.copyfile(assets.source,app.data/outputs[0]);shutil.copyfile(assets.audio,app.data/refs[-1]['path'])
        record=checkpoint(app.data,original)
        for key in ('timeline','outputs','parameters','prompts'):record[key]=record[key][:1]
        record['timeline'][0].update(duration=4,frames=96);record['parameters'][0].update(width=320,height=180)
        record.update(completed=1,audio_start=0);save(app.data/'outputs'/original,record)
        row=app.store.one('SELECT j.message_id,m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=?',(original,))
        meta=json.loads(row['meta']);meta['video_parameters']['duration']=4
        app.store.execute('UPDATE messages SET meta=? WHERE id=?',(json.dumps(meta),row['message_id']))
        with patch.object(app.engine,'require_model',return_value={'name':'Synthetic LLM'}):
            ident=request(app,chat,{'action':'infographic','source':original,'clip':1,'start':1,'end':3,
                'prompt':'Add a title at 0.4 seconds, keep the background video.'})['job_id']
        job=app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));payload=json.loads(job['payload']);settings=payload['settings'];cancel=threading.Event()
        log=app.data/'smoke.log';stage=lambda _:None
        excerpt=prepare_infographic(app,job,settings,cancel,stage,log);payload['media']=[excerpt]
        plan={'title':'Timeline test','visual_direction':'Transparent background, large readable white title','delivery':'serious','music_style':'','jingle_lyrics':'',
            'scenes':[{'title':'Overlay','purpose':'Title over video','narration':'Un titolo sopra il video originale.'}]}
        html='<style>body{margin:0;width:1280px;height:720px;background:transparent;position:relative}h1{position:absolute;left:90px;top:80px;color:white;font:700 90px Arial;text-shadow:0 2px 12px black}</style><h1 data-motion="fade" data-start="0.4" data-duration="0.4">TIMELINE</h1>'
        def complete(messages,settings,cancel,on_text=None,schema=None):
            if schema:return json.dumps(plan),'stop'
            if on_text:on_text(html)
            return html,'stop'
        with patch.object(app.engine,'start_llama'),patch.object(app.engine,'stop'),patch.object(app.engine,'chat_messages',return_value=[{'role':'user','content':payload['prompt']}]),patch.object(app.engine,'completion',side_effect=complete):
            artifact=build(app,job,payload,[{'role':'user','content':payload['prompt'],'media':[excerpt]}],settings,{},cancel,stage,log,{})
        app.store.update_answer(job,'Synthetic infographic','done',[],{'artifact':artifact});app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        saved=app.store.canvas_history.get(chat)
        result=use_infographic(app,chat,{'artifact_id':saved['id']})
        app.execute_job(app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],)),cancel)
        message=app.store.chat(chat)['messages'][-1]
        assert message['status']=='done',message['content']
        manifest=describe(app,chat,result['job_id']);assert len(manifest['clips'][0]['versions'])==2
        video=app.data/message['media'][0]['path']
        with av.open(str(video)) as movie:
            stream=movie.streams.video[0]
            assert (stream.width,stream.height,stream.frames,float(stream.average_rate))==(320,180,96,24)
            assert movie.streams.audio
        destination=ROOT/'work/clip-tools-qa';destination.mkdir(exist_ok=True)
        shutil.copyfile(video,destination/'timeline-roundtrip.mp4')
        infographic=next(m for m in artifact['media'] if m['path'].endswith('/infografica.mp4'))
        with av.open(str(app.data/infographic['path'])) as movie:
            assert movie.streams.video[0].frames==48
            assert (movie.streams.video[0].width,movie.streams.video[0].height)==(320,180)
        print(json.dumps({'passed':True,'infographic_duration':2,'timeline_duration':4,'frames':96,'fps':24,'audio_preserved':True,
            'selected_clip':1,'source_interval':[1,3],'versions':2,'preview':str(destination/'timeline-roundtrip.mp4')}))
    finally:fixture.tearDown();assets.tearDown()


if __name__=='__main__':main()
