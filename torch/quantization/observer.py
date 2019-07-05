from __future__ import absolute_import, division, print_function, unicode_literals
import torch.nn as nn
import torch
from functools import partial

class Observer(nn.Module):
    r"""Default Observer Module
    A default implementation of the observer module, only works for
    `per_tensor_affine` quantization scheme.
    The module will record the running average of max and min value of the
    observed Tensor and calulate_qparams will calculate the scale and zero_point

    Other types of Observers should follow the same API, it can take arbitrary
    number of keyward arguments. In forward, it will update the statistics of
    the observed Tensor. And it should provide a `calculate_qparam` function
    that computes the quantization parameters given the collected statistics.
    TODO: Maybe add an abstract Observer class that enforces these rules?
    """
    def __init__(self, dtype=torch.quint8, qscheme=torch.per_tensor_affine):
        super(Observer, self).__init__()
        self.dtype = dtype
        self.qscheme = qscheme
        assert self.qscheme in (torch.per_tensor_affine, torch.per_tensor_symmetric), \
            'Default Observer only works for per_tensor_affine and \
                per_tensor_symmetric quantization scheme'
        self.min_val = None
        self.max_val = None

    def forward(self, x):
        if self.min_val is None or self.max_val is None:
            self.min_val = torch.min(x)
            self.max_val = torch.max(x)
        else:
            self.min_val = torch.min(torch.min(x), self.min_val)
            self.max_val = torch.max(torch.max(x), self.max_val)

    def calculate_qparams(self):
        if self.dtype == torch.qint8:
            qmin, qmax = -128, 127
        else:
            qmin, qmax = 0, 255
        if self.qscheme == torch.per_tensor_symmetric:
            max_val = torch.max(-self.min_val, self.max_val)
            min_val = -max_val * (128.0 / 127.0)
        else:
            max_val = self.max_val
            min_val = self.min_val
        n_levels = 255.0
        scale = (max_val - min_val) / n_levels
        zero_point = qmin - torch.round(min_val / scale)
        zero_point = max(qmin, zero_point)
        zero_point = min(qmax, zero_point)

        return torch.tensor([scale, zero_point])

def observer(observer_cls, **kwargs):
    return partial(observer_cls, **kwargs)

def default_observer(**kwargs):
    return observer(Observer, **kwargs)

def default_weight_observer(**kwargs):
    kwargs.setdefault('dtype', torch.qint8)
    kwargs.setdefault('qscheme', torch.per_tensor_symmetric)
    return observer(Observer, **kwargs)
