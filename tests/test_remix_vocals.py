import sys,unittest
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"native"))
from remix import resinging

class VocalAlignmentTests(unittest.TestCase):
 def test_resing_preflight_accepts_five_minutes_without_trimming(self):
   for duration in (3,240,300,300.5):
    app=SimpleNamespace(original=Path('source.wav'),audio_info=lambda _: {'duration':duration})
    source,info,start,end=resinging.preflight(app,{})
    self.assertEqual((source,start,end),(app.original,0,duration));self.assertEqual(info['duration'],duration)
   for duration in (2.9,300.6):
    app=SimpleNamespace(original=Path('source.wav'),audio_info=lambda _: {'duration':duration})
    with self.assertRaisesRegex(ValueError,'5 minuti'):resinging.preflight(app,{})

 def test_alignment_accepts_constant_positive_and_negative_delays_and_repeated_notes(self):
   original = [(i*.4,i*.4+.3,60+i%5) for i in range(30)]
   for delay in (.12, -.1):
    generated = [(a+delay+(.005 if i%2 else 0),b+delay,p) for i,(a,b,p) in enumerate(original)]
    report=resinging.alignment(original,generated)
    self.assertEqual(report['matching_notes'],30);self.assertAlmostEqual(report['vocal_delay_seconds'],delay,delta=.005)
   generated=original[:8]+[(3.1,3.15,62)]+original[8:]
   self.assertEqual(resinging.alignment(original,generated)['matching_notes'],30)
 def test_alignment_rejects_wrong_melody_and_tempo_drift(self):
   original = [(i*.4,i*.4+.3,60+i%5) for i in range(30)]
   for generated in ([],[(a,b,p+12) for a,b,p in original],[(a*1.1,b*1.1,p) for a,b,p in original],[(a+3,b+3,p) for a,b,p in original]):
    with self.subTest(generated=len(generated)), self.assertRaises(ValueError): resinging.alignment(original,generated)
 def test_phrase_alignment_repairs_different_anticipations_or_delays(self):
   for shifts in ((.44,.74,.51),(-.44,-.74,-.51)):
    a,b=self.phrase_notes(shifts);report=resinging.alignment(a,b)
    self.assertEqual(report['phrases'],3)
    self.assertGreater(report['p90_onset_error_seconds'],.2)
    self.assertLess(report['predicted_corrected_timing']['max_onset_error_seconds'],1e-8)
    self.assertTrue(.85<=report['min_gap_tempo']<=report['max_gap_tempo']<=1.18)
    points=resinging.phrase_intervals(report,25,25)
    self.assertTrue(all(y['source']>x['source'] and y['target']>x['target'] for x,y in zip(points,points[1:])))
    with self.assertRaises(ValueError):resinging.alignment(a,b,allow_phrases=False)
 def test_phrase_alignment_keeps_safety_for_large_or_unreliable_changes(self):
   for shifts in ((0,2,0),(0,3,0)):
    a,b=self.phrase_notes(shifts)
    with self.assertRaises(ValueError):resinging.alignment(a,b)
   a,b=self.phrase_notes((.44,.74,.51))
   b=[(x,y,p+12) for x,y,p in b]
   with self.assertRaisesRegex(ValueError,'melodia'):resinging.alignment(a,b)
 def test_long_pauses_can_absorb_offset_changes_without_stretching_phrases(self):
   original=[];generated=[]
   for phrase,shift in enumerate((.08,1.91,1.6)):
    for i in range(8):
     a=10+phrase*30+i*.4;p=60+i%5
     original.append((a,a+.3,p));generated.append((a+shift,a+.3+shift,p))
   report=resinging.alignment(original,generated)
   self.assertEqual(report['phrases'],3)
   self.assertGreater(max(g[0]-o[0] for o,g in zip(original,generated))-min(g[0]-o[0] for o,g in zip(original,generated)),1.5)
   self.assertTrue(.85<=report['min_gap_tempo']<=report['max_gap_tempo']<=1.18)
   self.assertLess(report['predicted_corrected_timing']['max_onset_error_seconds'],1e-8)
 def test_repeated_notes_cannot_jump_to_another_refrain(self):
   original=[];generated=[]
   for start in (10,40,70):
    phrase=[(start+i*.24,start+i*.24+.23,77 if i<16 else 72) for i in range(17)]
    original.extend(phrase);generated.extend(phrase[1:] if start==40 else phrase)
   report=resinging.alignment(original,generated,allow_phrases=False,verification=True)
   self.assertAlmostEqual(report['vocal_delay_seconds'],0)
   self.assertLess(report['p90_onset_error_seconds'],.01)
   pairs=resinging.matched_notes(original,generated,verification=True)
   self.assertTrue(all(abs(o[0]-g[0])<.01 for o,g in pairs))
 def test_good_total_coverage_cannot_hide_a_missing_refrain(self):
   original,generated=self.phrase_notes((0,0,0,0))
   generated=generated[:8]+generated[16:]
   with self.assertRaisesRegex(ValueError,'frase'):
    resinging.alignment(original,generated,allow_phrases=False,verification=True)
 def test_small_uniform_tempo_drift_is_corrected_across_song_lengths(self):
   for seconds in (24.94,119.095,149.9,150.1,217.316,240):
    for scale in (.982,1.018):
     with self.subTest(seconds=seconds,scale=scale):
      original,generated=self.tempo_notes(seconds,scale)
      if seconds<30:
       # The short case still meets the existing constant-delay tolerance.
       self.assertEqual(resinging.alignment(original,generated),resinging.phrase_alignment(original,generated))
      else:
       report=resinging.alignment(original,generated)
       self.assertAlmostEqual(report['tempo_scale'],scale,places=8)
       self.assertEqual(report['matching_notes'],len(original))
       self.assertLess(report['predicted_corrected_timing']['max_onset_error_seconds'],1e-8)
       with self.assertRaises(ValueError):resinging.alignment(original,generated,allow_phrases=False,verification=True)
 def test_previously_good_constant_alignments_keep_the_same_path_below_and_above_150_seconds(self):
   for seconds in (12,24.94,89.513,119.095,149.9,150,150.1,185.156,217.316,240):
    original,generated=self.tempo_notes(seconds,1.,.1)
    self.assertEqual(resinging.alignment(original,generated),resinging.phrase_alignment(original,generated))
    self.assertNotIn('tempo_scale',resinging.alignment(original,generated))
 def test_tempo_correction_does_not_accept_large_changes_or_wrong_melodies(self):
   for scale,offset,transpose in ((.96,.4,0),(1.04,.4,0),(.982,3.,0),(.982,.4,12)):
    original,generated=self.tempo_notes(120,scale,offset)
    generated=[(a,b,p+transpose) for a,b,p in generated]
    with self.subTest(scale=scale,offset=offset,transpose=transpose),self.assertRaises(ValueError):resinging.alignment(original,generated)

 def phrase_notes(self, shifts):
   original=[];generated=[]
   for phrase,shift in enumerate(shifts):
    for i in range(8):
     a=2+phrase*8+i*.4;p=60+i%5
     original.append((a,a+.3,p));generated.append((a+shift,a+.3+shift,p))
   return original,generated

 def tempo_notes(self,seconds,scale=1.,offset=.4):
   original=[(2+i*.35,2+i*.35+.28,60+(i*13)%17) for i in range(max(20,int((seconds-5)/.35)))]
   return original,[(scale*a+offset,scale*b+offset,p) for a,b,p in original]
