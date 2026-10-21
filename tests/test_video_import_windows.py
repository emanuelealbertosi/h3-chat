import unittest
from h3chat.video_import_windows import windows


class ImportWindowsTests(unittest.TestCase):
    def test_fractional_tail_preserves_every_frame_and_soundtrack_clock(self):
        for size in (10, 15):
            for tail in range(1, 24):
                total = 25 * size * 24 + tail
                parts = windows(total, size)
                self.assertEqual(len(parts), 26)
                cursor = 0
                for start, count in parts:
                    self.assertEqual(start, cursor)
                    self.assertTrue(24 <= count <= size * 24)
                    cursor += count
                self.assertEqual(cursor, total)
                self.assertEqual(parts[-1], (total-24, 24))

    def test_existing_legal_boundaries_and_exact_multiples_are_unchanged(self):
        self.assertEqual(windows(31*24), [(0,360), (360,360), (720,24)])
        self.assertEqual(windows(30*24), [(0,360), (360,360)])
        self.assertEqual(windows(24), [(0,24)])

    def test_reported_375_point_833_second_movie_has_no_empty_window(self):
        parts = windows(9020)
        self.assertEqual(parts[-2:], [(8640,356), (8996,24)])
        self.assertEqual(sum(n for _,n in parts),9020)
