"""CPU audio regressions ported from H3-Music synchronization checks."""
import array,math,subprocess,tempfile,unittest,wave
from pathlib import Path
import test_remix_vocals as fixture
from remix import resinging
FFMPEG=Path(__file__).resolve().parents[1]/'runtime/remix/ffmpeg.exe'

@unittest.skipUnless(FFMPEG.is_file(),'Bundled FFmpeg is not installed')
class ResingAudioTests(unittest.TestCase):
 phrase_notes=fixture.VocalAlignmentTests.phrase_notes
 tempo_notes=fixture.VocalAlignmentTests.tempo_notes
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()

 def test_real_phrase_render_preserves_pitch_onsets_and_sample_duration(self):
     original, generated = self.phrase_notes((-0.44, -0.74, -0.51))
     report = resinging.alignment(original, generated)
     rate = 48000
     seconds = 25
     samples = array.array('h', [0]) * (seconds * rate)
     for a, b, _ in generated:
         for i in range(round(a * rate), round(b * rate)):
             samples[i] = round(9000 * math.sin(2 * math.pi * 440 * (i / rate - a)))
     source = self.data / 'source-phrases.wav'
     with wave.open(str(source), 'wb') as f:
         f.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
         f.writeframes(samples.tobytes())
     out = self.data / 'aligned.wav'

     def ff(args, *_):
         subprocess.run([str(FFMPEG), '-y', '-v', 'error', *map(str, args)], check=True, capture_output=True)
     resinging.render_aligned_voice(None, source, out, report, seconds, seconds, ff)
     pcm = self.data / 'checked.wav'
     ff(['-i', out, '-ac', '1', '-c:a', 'pcm_s16le', pcm])
     with wave.open(str(pcm), 'rb') as f:
         self.assertEqual(f.getnframes(), seconds * rate)
         values = array.array('h')
         values.frombytes(f.readframes(f.getnframes()))
     for a, b, _ in original:
         signal = values[round((a + 0.07) * rate):round((a + 0.17) * rate)]
         before = values[round((a - 0.06) * rate):round((a - 0.02) * rate)]
         self.assertGreater(math.sqrt(sum((x * x for x in signal)) / len(signal)), 3000)
         self.assertLess(math.sqrt(sum((x * x for x in before)) / len(before)), 100, msg=f'Onset {a}')
         crossings = sum((x <= 0 < y for x, y in zip(signal, signal[1:])))
         self.assertAlmostEqual(crossings / 0.1, 440, delta=15)

 def test_real_tempo_render_preserves_pitch_onsets_and_sample_duration(self):
     original, generated = self.tempo_notes(27.5, 0.975, 0.35)
     report = resinging.alignment(original, generated)
     rate = 48000
     seconds = 28
     self.assertAlmostEqual(report['tempo_scale'], 0.975, places=8)
     samples = array.array('h', [0]) * (seconds * rate)
     for a, b, _ in generated:
         for i in range(round(a * rate), round(b * rate)):
             samples[i] = round(9000 * math.sin(2 * math.pi * 440 * (i / rate - a)))
     source = self.data / 'tempo-source.wav'
     with wave.open(str(source), 'wb') as f:
         f.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
         f.writeframes(samples.tobytes())
     out = self.data / 'tempo-aligned.wav'

     def ff(args, *_):
         subprocess.run([str(FFMPEG), '-y', '-v', 'error', *map(str, args)], check=True, capture_output=True)
     resinging.render_aligned_voice(None, source, out, report, seconds, seconds, ff)
     pcm = self.data / 'tempo-checked.wav'
     ff(['-i', out, '-ac', '1', '-c:a', 'pcm_s16le', pcm])
     with wave.open(str(pcm), 'rb') as f:
         self.assertEqual(f.getnframes(), seconds * rate)
         values = array.array('h')
         values.frombytes(f.readframes(f.getnframes()))
     for a, b, _ in original:
         signal = values[round((a + 0.07) * rate):round((a + 0.17) * rate)]
         self.assertGreater(math.sqrt(sum((x * x for x in signal)) / len(signal)), 3000)
         crossings = sum((x <= 0 < y for x, y in zip(signal, signal[1:])))
         self.assertAlmostEqual(crossings / 0.1, 440, delta=15)
         onsets = []
         for delta in range(-7, 9):
             begin = round((a + delta * 0.01) * rate)
             block = values[begin:begin + rate // 100]
             if math.sqrt(sum((x * x for x in block)) / len(block)) > 1000:
                 onsets.append(delta * 0.01)
         self.assertTrue(onsets)
         self.assertLessEqual(abs(min(onsets)), 0.04)

 def test_negative_delay_keeps_added_silence_and_exact_duration_at_both_input_rates(self):
     for rate in (44100, 48000):
         for scale in (1.0, 1.0046):
             with self.subTest(rate=rate, scale=scale):
                 samples = array.array('h', [0]) * (rate * 3)
                 for i in range(round(rate * 0.5), round(rate * 0.8)):
                     samples[i] = round(9000 * math.sin(2 * math.pi * 440 * (i / rate - 0.5)))
                 source = self.data / f'early-{rate}-{scale}.wav'
                 with wave.open(str(source), 'wb') as f:
                     f.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
                     f.writeframes(samples.tobytes())
                 out = self.data / 'delayed.wav'
                 report = {'vocal_delay_seconds': -0.39431}
                 if scale != 1:
                     report['tempo_scale'] = scale

                 def ff(args, *_):
                     subprocess.run([str(FFMPEG), '-y', '-v', 'error', *map(str, args)], check=True, capture_output=True)
                 resinging.render_aligned_voice(None, source, out, report, 3, 3, ff)
                 pcm = self.data / 'delayed-checked.wav'
                 ff(['-i', out, '-ac', '1', '-c:a', 'pcm_s16le', pcm])
                 with wave.open(str(pcm), 'rb') as f:
                     self.assertEqual(f.getnframes(), 3 * 48000)
                     values = array.array('h')
                     values.frombytes(f.readframes(f.getnframes()))
                 onset = next((i / 48000 for i, value in enumerate(values) if abs(value) > 1000))
                 self.assertAlmostEqual(onset, (0.5 + 0.39431) / scale, delta=0.03)
                 self.assertEqual(max(map(abs, values[:round(0.7 * 48000)])), 0)
