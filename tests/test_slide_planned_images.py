import threading
import unittest
from unittest.mock import Mock
from h3chat.slide_html import include_planned_images,used_images


class PlannedImageTests(unittest.TestCase):
    def test_only_real_image_elements_count_as_used_assets(self):
        self.assertEqual(used_images('<style>/* <img data-asset-id="fake"> */</style><!-- <img data-asset-id="comment"> --><img data-asset-id=actual>'),{'actual'})

    def test_missing_image_gets_one_llm_repair_without_image_generation(self):
        engine=Mock();engine.completion.return_value=('<main><h1>Original</h1><img data-asset-id="planned"></main>','stop')
        progress=Mock();stage=Mock();request=[{'role':'user','content':'Slide originale'}]
        html,missing=include_planned_images(engine,request,{},threading.Event(),'<main><h1>Original</h1></main>',[{'id':'planned','description':'Una figura'}],progress,stage,7)
        self.assertFalse(missing);self.assertIn('planned',html);engine.completion.assert_called_once();engine.generate.assert_not_called()
        self.assertEqual(engine.completion.call_args.kwargs['on_text'],progress)
        self.assertIn('planned',engine.completion.call_args.args[0][-1]['content'])
        self.assertEqual(request,[{'role':'user','content':'Slide originale'}])

    def test_complete_or_unillustrated_pages_are_left_verbatim(self):
        engine=Mock();html='<main><img data-asset-id="planned"></main>'
        for planned in ([],[{'id':'planned'}]):
            self.assertEqual(include_planned_images(engine,[],{},threading.Event(),html,planned,Mock(),Mock(),1),(html,False))
        engine.completion.assert_not_called()

    def test_model_ignoring_repair_is_reported_without_unbounded_retries(self):
        engine=Mock();engine.completion.return_value=('<main>Ancora senza figura</main>','stop')
        _,missing=include_planned_images(engine,[],{},threading.Event(),'<main>Prima</main>',[{'id':'planned'}],Mock(),Mock(),1)
        self.assertTrue(missing);engine.completion.assert_called_once()

    def test_incomplete_repair_keeps_the_existing_incomplete_page_error(self):
        engine=Mock();engine.completion.return_value=('<main>Parziale','length')
        with self.assertRaisesRegex(ValueError,'Slide 7 incompleta'):
            include_planned_images(engine,[],{},threading.Event(),'<main>Prima</main>',[{'id':'planned'}],Mock(),Mock(),7)
