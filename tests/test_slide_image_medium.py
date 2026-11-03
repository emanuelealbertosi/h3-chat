import unittest
from h3chat.slide_style import image_prompt

class ImageMediumTests(unittest.TestCase):
    def test_photo_medium_is_preserved_without_forcing_an_illustration(self):
        prompt='Photorealistic historical reconstruction, natural skin texture, cinematic lighting'
        for form in ('tags','prose'):
            with self.subTest(form=form):
                actual=image_prompt(prompt,'professional',form)
                self.assertTrue(actual.startswith(prompt))
                self.assertNotIn('Illustration only',actual)
                self.assertNotIn('text-free illustration',actual)
                self.assertIn('no text',actual)

    def test_comic_direction_still_keeps_its_explicit_visual_style(self):
        actual=image_prompt('A school laboratory','comic','prose')
        self.assertIn('ink outlines',actual)
        self.assertIn('no typography',actual)
