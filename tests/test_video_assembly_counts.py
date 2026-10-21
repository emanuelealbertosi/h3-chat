"""A 37-clip source preparation batch must still assemble the full 64-clip film."""
import copy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from h3chat.video_assemble import render


class AssemblyCountsTests(unittest.TestCase):
    def test_27_modified_plus_37_originals_assembles_all_64_without_models(self):
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder);audio={'id':'a'*32,'path':'song.wav','mime':'audio/wav'};(data/'song.wav').write_bytes(b'audio')
            timeline=[{'index':n,'start':n*10,'duration':10,'frames':240,'images':[]} for n in range(64)]
            outputs=[f'prepared/clip-{n+1:03}.mp4' for n in range(64)];(data/'prepared').mkdir()
            for path in outputs[:27]:(data/path).write_bytes(b'generated video')
            (data/'original.mov').write_bytes(b'original video')
            record={'timeline':timeline,'outputs':outputs,'parameters':[{'steps':12} for _ in timeline],'prompts':['Original' for _ in timeline],
                'clip_sources':[None]*27+[{'path':'original.mov','start':n*10} for n in range(27,64)],'completed':64,
                'working_timeline':True,'edited_clips':list(range(1,28)),'revision_completed':list(range(1,28)),
                'plan':{'prompt':'Film','images':[],'audios':[{'index':1,'role':'reuse','start':0}]}}
            value={'record':record,'audio':audio,'duration':640,'meta':{'video_parameters':{}},'refs':[audio]}
            originals={p:(data/p).read_bytes() for p in outputs[:27]};stages=[];requests=[]
            def tool(name,body,*args,**kwargs):
                requests.append(body)
                for scene in body['timeline']:Path(scene['output']).write_bytes(b'extracted source')
                return {'clips':len(body['timeline'])}
            engine=SimpleNamespace(tool_call=Mock(side_effect=tool),generate_video=Mock(side_effect=AssertionError('No GPU generation')))
            app=SimpleNamespace(data=data,engine=engine,store=SimpleNamespace(update_answer=Mock(),execute=Mock()))
            job={'id':'b'*32,'chat_id':'c'*32};settings={'_video_assemble':'d'*32}
            def compose(engine,files,*args,**kwargs):
                self.assertEqual(files,[data/p for p in outputs]);self.assertEqual(len(files),64)
                self.assertTrue(all(p.exists() for p in files));return {'duration':640}
            with patch('h3chat.video_assemble.source',return_value=value),patch('h3chat.video_versions.choices',return_value={}),patch('h3chat.video_versions.apply'),patch('h3chat.video_import.repair_import_audio'),patch('h3chat.soundtrack.compose',side_effect=compose) as mux:
                render(app,job,{},settings,threading.Event(),stages.append,data/'log')
            self.assertEqual(len(requests),1);batch=requests[0]
            self.assertEqual([s['index']+1 for s in batch['timeline']],list(range(28,65)))
            self.assertEqual((batch['timeline_total'],batch['prepare_total'],batch['prepare_offset']),(64,37,0))
            self.assertTrue(any('64 clip totali' in s and '37 tratti originali' in s for s in stages))
            self.assertTrue(any('tutte le 64 clip' in s for s in stages))
            self.assertEqual({p:(data/p).read_bytes() for p in outputs[:27]},originals)
            saved=json.loads((data/'outputs'/job['id']/'scenes.json').read_text())
            self.assertEqual(len(saved['timeline']),64);self.assertEqual(saved['outputs'],outputs)
            self.assertEqual(app.store.update_answer.call_args.args[4]['video_parameters']['scenes'],64)
            engine.generate_video.assert_not_called();mux.assert_called_once()

    def test_source_groups_keep_one_global_preparation_counter(self):
        from h3chat.video_import import prepare
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder);(data/'first').mkdir();(data/'second').mkdir()
            record={'timeline':[{'index':n,'start':n,'duration':1,'frames':24} for n in range(4)],'outputs':['first/a.mp4','second/b.mp4','first/c.mp4','second/d.mp4'],
                'clip_sources':[None,{'path':'source1.mov','start':0},{'path':'source2.mov','start':0},{'path':'source1.mov','start':1}]}
            app=SimpleNamespace(data=data,engine=SimpleNamespace(tool_call=Mock()))
            prepare(app,{'record':record},threading.Event(),Mock(),data/'log')
            batches=[c.args[1] for c in app.engine.tool_call.call_args_list]
            self.assertEqual([(b['timeline_total'],b['prepare_total'],b['prepare_offset']) for b in batches],[(4,3,0),(4,3,2)])


if __name__=='__main__':unittest.main()
