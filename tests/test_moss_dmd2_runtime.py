import unittest
try:import torch
except ModuleNotFoundError as error:
    if error.name!='torch':raise
    torch=None
from types import SimpleNamespace
from unittest.mock import patch
from h3chat.moss_dmd2_runtime import Adapter,cached_adapter


class ResidualTests(unittest.TestCase):
    def test_adapter_is_reloaded_after_model_unload_clears_its_value(self):
        worker=SimpleNamespace(dmd2_adapter=None,dmd2_path='same-file')
        with patch('h3chat.moss_dmd2_runtime.Adapter') as create:
            first=cached_adapter(worker,'same-file');self.assertIs(cached_adapter(worker,'same-file'),first)
            self.assertEqual(create.call_count,1)
            worker.dmd2_adapter=None
            cached_adapter(worker,'same-file');self.assertEqual(create.call_count,2)

    def model(self):
        m=torch.nn.Module();m.layers=torch.nn.ModuleList([torch.nn.Module()])
        m.layers[0].proj=torch.nn.ModuleDict({'q':torch.nn.Linear(4,3,bias=False,dtype=torch.bfloat16)})
        m.layers[0].proj['q'].weight.data.fill_(.001)
        return m

    @unittest.skipUnless(torch is not None,'Install the optional image runtime to run the CPU PyTorch adapter checks')
    def test_unmerged_fp32_delta_changes_output_then_is_fully_removed(self):
        m=self.model();linear=m.layers[0].proj['q'];x=torch.ones(1,4,dtype=torch.bfloat16)
        original=linear.weight.detach().clone();baseline=linear(x)
        adapter=Adapter.__new__(Adapter);adapter.layers={'layers.0.proj.q':(torch.full((2,4),.1),torch.full((3,2),.1),1.)}
        with adapter.apply(m) as report:
            observed=linear(x);self.assertEqual(report['applied_modules'],1);self.assertFalse(report['merge'])
            expected=baseline+(x.float()@adapter.layers['layers.0.proj.q'][0].T@adapter.layers['layers.0.proj.q'][1].T).to(baseline.dtype)
            torch.testing.assert_close(observed,expected);self.assertFalse(torch.equal(observed,baseline))
        self.assertEqual(len(linear._forward_hooks),0)
        self.assertTrue(torch.equal(linear.weight,original));torch.testing.assert_close(linear(x),baseline)
        with self.assertRaisesRegex(RuntimeError,'intentional'):
            with adapter.apply(m):raise RuntimeError('intentional')
        self.assertEqual(len(linear._forward_hooks),0)

    @unittest.skipUnless(torch is not None,'Install the optional image runtime to run the CPU PyTorch adapter checks')
    def test_invalid_target_fails_before_any_hook_is_installed(self):
        m=self.model();adapter=Adapter.__new__(Adapter)
        adapter.layers={'layers.0.proj.q':(torch.ones(2,4),torch.ones(3,2),1.),'layers.0.proj.missing':(torch.ones(2,4),torch.ones(3,2),1.)}
        with self.assertRaises(ValueError):
            with adapter.apply(m):pass
        self.assertEqual(len(m.layers[0].proj['q']._forward_hooks),0)


if __name__=='__main__':unittest.main()
