"""Reference-to-latent path and denoise contract without loading GPU models."""
from types import SimpleNamespace
from unittest.mock import Mock,patch
import math,unittest
from h3chat.moss_img2img import canvas,encode
import test_vision_memory_phases as phases


class MossImg2ImgTests(unittest.TestCase):
    def test_auto_aspect_keeps_area_explicit_canvas_wins_and_extreme_fails(self):
        w,h=canvas(1024,1024,1600,900)
        self.assertLess(abs(w/h-16/9),.01);self.assertGreaterEqual(w*h,1024**2)
        self.assertEqual(canvas(1500,1500,1600,900,False),(1500,1500))
        with self.assertRaises(ValueError):canvas(1024,1024,8192,20)

    def test_worker_uses_vae_encoded_source_instead_of_empty_latent(self):
        instance=phases.worker_class()();instance.architecture='moss'
        instance.encode.__func__.__globals__['math']=math
        instance.torch=SimpleNamespace(zeros=Mock(return_value='empty'))
        instance.comfy=SimpleNamespace(utils=SimpleNamespace(common_upscale=Mock()),
            model_management=SimpleNamespace(intermediate_device=lambda:'cpu'))
        instance.vae=object();clip=SimpleNamespace(tokenize=Mock(side_effect=lambda text:text),
            encode_from_tokens_scheduled=Mock(side_effect=lambda text:[text]))
        image=SimpleNamespace(shape=(1,300,600,3));request={'width':512,'height':512,'prompt':'painted landscape'}
        with patch('h3chat.moss_img2img.encode',return_value='source-latent') as vae:
            result=instance.encode(clip,request,[image])
        self.assertEqual(result[-1],'source-latent');instance.torch.zeros.assert_not_called()
        self.assertEqual(vae.call_args.args[:2],(instance.vae,image))
        self.assertEqual(vae.call_args.args[2:],instance.canvas_size)
        self.assertAlmostEqual(instance.canvas_size[0]/instance.canvas_size[1],2,places=2)
        instance.encode(clip,request,[]);instance.torch.zeros.assert_called_once()
        with self.assertRaisesRegex(ValueError,'una sola'):instance.encode(clip,request,[image,image])

    def test_sampler_strength_applies_only_to_moss_with_source_and_is_reported(self):
        fixture=phases.MemoryPhaseTests()
        for arch,refs,expected in [('moss',[object()],.35),('moss',[],1),('ming',[object()],1)]:
            instance,_=fixture.fixture();instance.architecture=arch;instance.images=lambda paths:refs
            sample=Mock(wraps=instance.comfy.sample.sample);instance.comfy.sample.sample=sample
            original=instance.generate
            instance.generate=lambda request:original(request|{'strength':.35})
            with patch('h3chat.moss_image.sampling',side_effect=lambda model:model),patch('h3chat.image_canvas.crop_canvas',side_effect=lambda array,*size:array):
                fixture.generate(instance)
            self.assertEqual(sample.call_args.kwargs['denoise'],expected)
            emitted=original.__func__.__globals__['emit'].call_args
            self.assertEqual(emitted.args,('done',));self.assertEqual(emitted.kwargs['parameters']['strength'],expected)
            if arch=='moss':self.assertEqual(emitted.kwargs['parameters']['reference_mode'],'img2img-experimental' if refs else 'text-to-image')

    def test_rgba_source_is_composited_and_padded_without_stretching_output(self):
        try:import torch
        except ImportError:self.skipTest('CPU tensor check requires the optional image runtime')
        source=torch.zeros((1,320,512,4));source[...,0]=1
        # Transparent red becomes white before encoding, including padded edges.
        def upscale(image,w,h,method,crop):
            self.assertEqual((method,crop),('lanczos','center'))
            return torch.nn.functional.interpolate(image,size=(h,w),mode='nearest')
        vae=SimpleNamespace(encode=Mock(side_effect=lambda pixels:pixels))
        result=encode(vae,source,501,317,upscale=upscale,torch=torch)
        self.assertEqual(tuple(result.shape),(1,320,512,3));self.assertTrue(torch.all(result==1))


if __name__=='__main__':unittest.main()
