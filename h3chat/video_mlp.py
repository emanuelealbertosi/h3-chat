"""Bound H3's INT8 feed-forward workspace without changing its tokens.

No Torch import in the web process. INT8 activations have independent per-row
scales, so token batches preserve quantization and the fused SwiGLU operation.
Both projections are transferred once per block, not once per token batch.
"""
from types import MethodType


def require_supported_weights(diffusion):
    if any(getattr(weight, '_layout_cls', None) == 'AsymW4A8Int8Layout'
            for _, weight in diffusion.named_parameters()):
        raise ValueError('MiniMax H3 W4A8 non è supportato. Scegli una variante INT8.')


def supported(layer, ops):
    for linear in (layer.fc1, layer.fc2):
        weight = linear.weight
        if (not isinstance(weight, ops.QuantizedTensor)
                or weight._layout_cls != 'TensorWiseINT8Layout'
                or getattr(weight._params, 'transposed', False)
                or getattr(linear, '_full_precision_mm', False)
                or getattr(linear, 'comfy_force_cast_weights', False)
                or getattr(linear, 'pre_quant_scale', None) is not None
                or len(linear.weight_function) or len(linear.bias_function)):
            return False
    return True


def rows_per_chunk(layer, x, budget):
    # The first projection is the dominant workspace (two SwiGLU branches).
    row_bytes = layer.fc1.out_features * x.element_size()
    return max(16, budget // row_bytes // 16 * 16)


def run_chunked(layer, x, torch, ops, budget):
    rows = rows_per_chunk(layer, x, budget)
    flat = x.reshape(-1, x.shape[-1])
    # Keep both weights alive across batches using Comfy's synchronized
    # offload contexts. Do not cache CUDA weights on the model afterwards.
    with ops.CastBiasWeightContext(layer.fc1, input=None,
            dtype=layer.fc1.weight.dtype, device=x.device, bias_dtype=x.dtype,
            offloadable=True, compute_dtype=x.dtype, want_requant=True) as (w1, b1):
        with ops.CastBiasWeightContext(layer.fc2, x, offloadable=True,
                compute_dtype=x.dtype, want_requant=True) as (w2, b2):
            if (not isinstance(w1, ops.QuantizedTensor)
                    or not isinstance(w2, ops.QuantizedTensor)):
                raise RuntimeError('H3 quantized MLP: unexpected weight conversion.')
            def linear(value, original, bias, activation='none'):
                weight,scale=ops.TensorWiseINT8Layout.get_plain_tensors(original)
                return ops.quant_ops.ck.int8_linear(value, weight, scale, bias,
                    x.dtype, convrot=getattr(original._params, 'convrot', False),
                    convrot_groupsize=getattr(original._params, 'convrot_groupsize', 256),
                    input_act=activation)
            out = torch.empty_like(flat)
            for start in range(0, flat.shape[0], rows):
                end = min(start + rows, flat.shape[0])
                hidden = linear(flat[start:end], w1, b1)
                result = linear(hidden, w2, b2, 'swiglu')
                del hidden
                out[start:end].copy_(result)
                del result
            return out.reshape(x.shape)


def install(diffusion, torch, ops, budget=512 * 1024**2):
    count = 0
    for block in diffusion.blocks:
        layer = block.mlp
        if hasattr(layer, '_h3_original_forward') or not supported(layer, ops):
            continue
        layer._h3_original_forward = layer.forward
        def forward(self, x):
            if (x.requires_grad or x.device.type != 'cuda'
                    or not supported(self, ops)
                    or x.numel() // x.shape[-1] <= rows_per_chunk(self, x, budget)):
                return self._h3_original_forward(x)
            return run_chunked(self, x, torch, ops, budget)
        layer.forward = MethodType(forward, layer)
        count += 1
    return count
