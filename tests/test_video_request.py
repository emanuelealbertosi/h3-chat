import ast
import hashlib
import io
import json
import math
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

import test_video as fixture
from h3chat.video_request import audio_window, repeated_scene, spoken_lines
from h3chat.video_timeline import scene_plan, timeline
from h3chat.video_engine import VideoEngine


class RequestTests(unittest.TestCase):
    def test_clip_one_overrides_full_song_without_treating_shot_ranges_as_audio(self):
        prompt='CLIP 1 OF 6 — ABSOLUTE TIMELINE 00:00–00:15\nFORMAT: 15 seconds, anime\nAUDIO: Use corresponding 00:00–00:15 segment.\n00:00–00:06 — INSTRUMENTAL\n00:06–00:09 — INSTRUMENTAL BUILDUP'
        self.assertEqual(audio_window(prompt,89.5),{'start':0,'duration':15,'source_duration':89.5,'explicit':True})
        self.assertEqual(len(timeline(audio_window(prompt,89.5)['duration'])),1)

    def test_later_segment_duration_only_and_full_track_default(self):
        self.assertEqual(audio_window('CLIP 2 — ABSOLUTE TIMELINE 00:15–00:30\nFORMAT: 15 seconds',90)['start'],15)
        self.assertEqual(audio_window('Video di 30 secondi con la canzone',90)['duration'],30)
        self.assertEqual(audio_window('Anima tutta la canzone',90),{'start':0,'duration':90,'source_duration':90,'explicit':False})
        self.assertEqual(audio_window('AUDIO: segmento 01:00–01:15',90)['start'],60)
        self.assertEqual(audio_window('00:00–00:06 — Primo piano\n00:06–00:09 — Sveglia',90)['duration'],90)
        self.assertEqual(audio_window('AUDIO: 00:00:15–00:00:30',90)['start'],15)

    def test_conflicting_invalid_or_unavailable_windows_fail_before_rendering(self):
        for prompt in ('FORMAT: 15 seconds\nAUDIO: 00:15–00:45','AUDIO: 00:15–00:10','AUDIO: 01:00–02:00','AUDIO: 00:70–00:80','TIMELINE 00:00–00:15\nAUDIO 00:15–00:30'):
            with self.subTest(prompt=prompt),self.assertRaises(ValueError):audio_window(prompt,90)
        with self.assertRaises(ValueError):audio_window('Video di 10 minuti',30)
        # A short requested window is also allowed inside a track longer than ten minutes.
        self.assertEqual(audio_window('FORMAT: 15 seconds',1000)['duration'],15)

    def test_complete_numbered_segments_are_scene_times_not_audio_crops(self):
        for label in ('SEGMENT','SEGMENTO','CLIP','SCENE','SCENA','SHOT','INQUADRATURA','BLOCCO NARRATIVO'):
            prompt=f'''COMPLETE 90-SECOND ANIME MUSIC VIDEO
TOTAL AUDIO DURATION: approximately 89.5 seconds.
VIDEO STRUCTURE: 6 consecutive 15-second generations.
# {label} 1 — 00:00–00:15
00:00–00:06 — INSTRUMENTAL
AUDIO: INSTRUMENTAL.
# {label} 2 — 00:15–00:30
# {label} 3 — 00:30–00:45
# {label} 4 — 00:45–01:00
# {label} 5 — 01:00–01:15
# {label} 6 — 01:15–01:29.544'''
            for storyboard in (False,True):
                with self.subTest(label=label,storyboard=storyboard):
                    self.assertEqual(audio_window(prompt,89.5416667,storyboard=storyboard),
                        {'start':0,'duration':89.5416667,'source_duration':89.5416667,'explicit':False})

    def test_explicit_master_window_remains_independent_of_numbered_scene_times(self):
        for scenes in ('SEGMENT 1 — 00:00–00:06',
                       'SEGMENT 1 — 00:00–00:06\nSEGMENT 2 — 00:06–00:15'):
            prompt='AUDIO: 00:15–00:30\n'+scenes
            self.assertEqual(audio_window(prompt,90,storyboard=True),
                {'start':15,'duration':15,'source_duration':90,'explicit':True})
            with self.assertRaisesRegex(ValueError,'intervalli audio diversi'):
                audio_window(prompt+'\nSOUNDTRACK: 00:30–00:45',90,storyboard=True)
        self.assertEqual(audio_window('SEGMENT 2 — 00:15–00:30',90)['start'],15)

    def test_copy_guard_and_verbatim_speech(self):
        opening='An aerial camera flies over the stone walls, enters the bedroom, and shows the teacher turning off his ringing alarm clock.'
        self.assertEqual(repeated_scene([],['Clip 1 '+opening,'Clip 2 '+opening],'A parody'),2)
        self.assertEqual(repeated_scene([opening],[opening.upper()],'A parody'),2)
        self.assertIsNone(repeated_scene([opening],[opening],'Ripeti questa scena'))
        self.assertEqual(repeated_scene([opening],[opening],'Do not repeat the opening'),2)
        self.assertIsNone(repeated_scene([opening],['The teacher leaves his bedroom and walks to school with his books.'],'A parody'))
        self.assertEqual(spoken_lines('00:09–00:12 — MALE VOCAL, EREN\n"Alle sette la sveglia suona"\n00:12–00:15 — MALE VOCAL, EREN\n"La spengo e mi rigiro nel letto"'),['Alle sette la sveglia suona','La spengo e mi rigiro nel letto'])

    def test_scene_audio_offsets_match_selected_segment(self):
        plan={'prompt':'Test','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
        self.assertEqual([scene_plan(plan,s,1,audio_start=30)['audios'][0]['start'] for s in timeline(30)],[30,45])

    def test_assistant_off_recognizes_singing_and_requested_mouth_movements(self):
        from h3chat.video_routing import direct_plan
        for prompt in ('Eren sings while staring at the alarm clock.','Accurate Italian mouth movements.'):
            self.assertEqual(direct_plan(prompt,[{'mime':'audio/wav'}],15)['audios'][0]['role'],'lipsync')


class RequestServiceTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def test_assistant_off_uses_requested_window_instead_of_full_song(self):
        import base64
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as f:f.setparams((1,2,8000,0,'NONE','NONE'));f.writeframes(b'\0\0'*8000)
        audio=self.app.upload({'name':'song.wav','data':base64.b64encode(buffer.getvalue()).decode()})
        for offset in (0,15):
            chat=self.app.store.create_chat()
            prompt=f'CLIP 1 OF 6 — ABSOLUTE TIMELINE 00:{offset:02}–00:{offset+15:02}\nFORMAT: 15 seconds\nUse original audio with lip-sync.'
            job_id=self.app.send(chat['id'],{'prompt':prompt,'media':[audio],'video':True,'assistant':False})['job_id']
            job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(job_id,))
            result={'id':'video','mime':'video/mp4','name':'video.mp4','path':'outputs/test/video.mp4','generation':{'duration':15}}
            with patch('h3chat.soundtrack.probe',return_value={'duration':89.5}),patch.object(self.app.engine,'generate_long_video',return_value=result) as generate,patch.object(self.app.engine,'start_llama') as llama:
                self.app.execute_job(job,threading.Event())
            settings=generate.call_args.args[1]
            self.assertEqual((settings['_video_duration'],settings['_video_audio_start'],settings['_video_audio_source_duration']),(15,offset,89.5))
            llama.assert_not_called()
            self.assertEqual(self.app.store.chat(chat['id'])['messages'][-1]['status'],'done')

    def test_assistant_recovers_exact_italian_lyrics_and_fails_safely_if_omitted_again(self):
        prompt='00:09–00:12 — MALE VOCAL\n"Alle sette la sveglia suona"'
        plan={'prompt':'The teacher sings.','images':[],'audios':[]}
        complete=plan|{'prompt':'The teacher sings <d>[Italian] Alle sette la sveglia suona</d>.'}
        engine=self.app.engine;settings=self.app.store.settings()
        with patch.object(engine,'require_model',return_value={'id':'chat','name':'Chat','vision':{'enabled':False}}),patch.object(engine,'start_llama'),patch.object(engine,'completion',side_effect=[(json.dumps(plan),'stop'),(json.dumps(complete),'stop')]) as completion:
            output,_=engine.refine_video([],prompt,[],self.model,settings,threading.Event(),self.folder/'log',Mock())
        self.assertEqual(output,complete);self.assertEqual(completion.call_count,2)
        with patch.object(engine,'require_model',return_value={'id':'chat','name':'Chat','vision':{'enabled':False}}),patch.object(engine,'start_llama'),patch.object(engine,'completion',return_value=(json.dumps(plan),'stop')):
            with self.assertRaisesRegex(ValueError,'parole.*Nessun video'):
                engine.refine_video([],prompt,[],self.model,settings,threading.Event(),self.folder/'log',Mock())


class ComposerSegmentTests(unittest.TestCase):
    def test_real_mux_selects_only_requested_second_and_preserves_source(self):
        import av
        import numpy as np
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'native/media-compose-worker.py').read_text(encoding='utf-8'))
        namespace={'__name__':'fixture','emit':lambda *a,**k:None}
        nodes=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef)) and not isinstance(n,ast.FunctionDef) or isinstance(n,ast.FunctionDef) and n.name in ('probe','compose')]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<worker fixture>','exec'),namespace)
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);video=folder/'video.mp4';audio=folder/'song.wav';output=folder/'result.mp4'
            with av.open(str(video),'w') as out:
                stream=out.add_stream('libx264',rate=12);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
                for i in range(12):
                    frame=av.VideoFrame.from_ndarray(np.full((64,64,3),i*10,dtype=np.uint8),format='rgb24');frame.pts=i
                    for packet in stream.encode(frame):out.mux(packet)
                for packet in stream.encode(None):out.mux(packet)
            signal=np.concatenate([.4*np.sin(2*np.pi*frequency*np.arange(8000)/8000) for frequency in (300,700,1100)])
            with wave.open(str(audio),'wb') as out:out.setparams((1,2,8000,0,'NONE','NONE'));out.writeframes((signal*32767).astype('<i2').tobytes())
            before=hashlib.sha256(audio.read_bytes()).digest()
            result=namespace['compose']([str(video)],str(audio),str(output),audio_start=1,audio_duration=1)
            self.assertEqual((result['duration'],result['audio_start'],result['frames']),(1,1,12))
            with av.open(str(output)) as source:
                self.assertAlmostEqual(source.duration/av.time_base,1,delta=.06)
                frames=[frame.to_ndarray()[0] for frame in source.decode(audio=0)]
            samples=np.concatenate(frames)[4800:38400];freq=np.fft.rfftfreq(len(samples),1/48000);peak=freq[np.argmax(abs(np.fft.rfft(samples)))]
            self.assertAlmostEqual(peak,700,delta=3)
            self.assertEqual(hashlib.sha256(audio.read_bytes()).digest(),before)
