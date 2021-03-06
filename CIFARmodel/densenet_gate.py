import math
import torch
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.parameter import Parameter
from collections import OrderedDict
import re

__all__ = ['DenseNet', 'densenet121', 'densenet169', 'densenet201', 'densenet161']


def densenet121(**kwargs):
    
    model = DenseNet(num_init_features=64, growth_rate=32, block_config=(6, 12, 24, 16),
                     **kwargs)

    return model


def densenet169(**kwargs):
    
    model = DenseNet(num_init_features=64, growth_rate=32, block_config=(6, 12, 32, 32),
                     **kwargs)

    return model


def densenet201(**kwargs):
   
    model = DenseNet(num_init_features=64, growth_rate=32, block_config=(6, 12, 48, 32),
                     **kwargs)

    return model


def densenet161(**kwargs):
   
    model = DenseNet(num_init_features=96, growth_rate=48, block_config=(6, 12, 36, 24),
                     **kwargs)

    return model

class BottleGate(nn.Module):
    def __init__(self, num_channels):
        super(BottleGate, self).__init__()
        self.num_channels = num_channels
        self.gate = Parameter(torch.Tensor(1, num_channels, 1, 1), requires_grad=False)

    def forward(self, input_tensor):
        output = input_tensor * self.gate
        return output

    def extra_repr(self):
        s = ('{num_channels}')
        return s.format(**self.__dict__)


class GrowthRateGate(nn.Module):
    def __init__(self, num_channels):
        super(GrowthRateGate, self).__init__()
        self.num_channels = num_channels
        self.gate = Parameter(torch.Tensor(1, num_channels, 1, 1), requires_grad=False)

    def forward(self, input_tensor):
        output = input_tensor * self.gate
        return output

    def extra_repr(self):
        s = ('{num_channels}')
        return s.format(**self.__dict__)


class LayerGate(nn.Module):
    def __init__(self):
        super(LayerGate, self).__init__()
        self.gate = Parameter(torch.tensor(1), requires_grad=False)

    def forward(self, input_tensor):
        output = input_tensor * self.gate
        return output

    def extra_repr(self):
        s = 'keep layer or not:'
        if self.gate.data.item() == 1:
            s += 'True'
        else: 
            s += 'False'
        return s


class _DenseLayer(nn.Sequential):
    def __init__(self, num_input_features, growth_rate, bn_size, drop_rate):
        super(_DenseLayer, self).__init__()
        self.add_module('norm1', nn.BatchNorm2d(num_input_features)),
        self.add_module('relu1', nn.ReLU(inplace=True)),
        self.add_module('conv1', nn.Conv2d(num_input_features, bn_size *
                        growth_rate, kernel_size=1, stride=1, bias=False)),
        self.add_module('bg', BottleGate(bn_size * growth_rate))
        self.add_module('norm2', nn.BatchNorm2d(bn_size * growth_rate)),
        self.add_module('relu2', nn.ReLU(inplace=True)),
        self.add_module('conv2', nn.Conv2d(bn_size * growth_rate, growth_rate,
                        kernel_size=3, stride=1, padding=1, bias=False)),
        self.add_module('grg', GrowthRateGate(growth_rate))
        self.add_module('lg', LayerGate())
        self.drop_rate = drop_rate

    def forward(self, x):
        new_features = super(_DenseLayer, self).forward(x)
        # if self.drop_rate > 0:
            # new_features = F.dropout(new_features, p=self.drop_rate, training=self.training)
        return torch.cat([x, new_features], 1)


class _DenseBlock(nn.Sequential):
    def __init__(self, num_layers, num_input_features, bn_size, growth_rate, drop_rate):
        super(_DenseBlock, self).__init__()
        for i in range(num_layers):
            layer = _DenseLayer(num_input_features + i * growth_rate, growth_rate, bn_size, drop_rate)
            self.add_module('denselayer%d' % (i + 1), layer)


class _Transition(nn.Sequential):
    def __init__(self, num_input_features, num_output_features):
        super(_Transition, self).__init__()
        self.add_module('norm', nn.BatchNorm2d(num_input_features))
        self.add_module('relu', nn.ReLU(inplace=True))
        self.add_module('conv', nn.Conv2d(num_input_features, num_output_features,
                                          kernel_size=1, stride=1, bias=False))
        self.add_module('pool', nn.AvgPool2d(kernel_size=2, stride=2))


class DenseNet(nn.Module):
    
    def __init__(self, growth_rate=12, block_config=(6, 12, 24, 16), compression=0.5,
                 num_init_features=24, bn_size=4, drop_rate=0, num_classes=1000, small_inputs=False):

        super(DenseNet, self).__init__()

        self.device = 'cpu'

        self.arch_sets = np.array([growth_rate, bn_size*growth_rate, block_config[0]])
        for config in block_config[1:]:
            self.arch_sets = np.vstack([self.arch_sets, [growth_rate, bn_size*growth_rate, config]])            

        self.gate_sets = self.arch_sets
        # print(self.gate_sets)

        self.compression = compression

        self.avgpool_size = 8 if small_inputs else 7

        if small_inputs:
            self.features = nn.Sequential(OrderedDict([
                ('conv0', nn.Conv2d(3, num_init_features, kernel_size=3, stride=1, padding=1, bias=False)),
            ]))
            self.img_size = 32
        else:
            self.features = nn.Sequential(OrderedDict([
                ('conv0', nn.Conv2d(3, num_init_features, kernel_size=7, stride=2, padding=3, bias=False)),
                ('norm0', nn.BatchNorm2d(num_init_features)),
                ('relu0', nn.ReLU(inplace=True)),
                ('pool0', nn.MaxPool2d(kernel_size=3, stride=2, padding=1)),
            ]))
            self.img_size = 224

        # Each denseblock
        num_features = num_init_features
        for i, num_layers in enumerate(block_config):
            block = _DenseBlock(num_layers=num_layers, num_input_features=num_features,
                                bn_size=bn_size, growth_rate=growth_rate, drop_rate=drop_rate)
            self.features.add_module('denseblock%d' % (i + 1), block)
            num_features = num_features + num_layers * growth_rate
            if i != len(block_config) - 1:
                trans = _Transition(num_input_features=num_features, num_output_features=int(num_features * compression))
                self.features.add_module('transition%d' % (i + 1), trans)
                num_features = int(num_features * compression)

        # Final batch norm
        self.features.add_module('norm_final', nn.BatchNorm2d(num_features))

        # Linear layer
        self.classifier = nn.Linear(num_features, num_classes)

        for name, param in self.named_parameters():
            if 'conv' in name and 'weight' in name:
                n = param.size(0) * param.size(2) * param.size(3)
                param.data.normal_().mul_(math.sqrt(2. / n))
            elif 'norm' in name and 'weight' in name:
                param.data.fill_(1)
            elif 'norm' in name and 'bias' in name:
                param.data.fill_(0)
            elif 'classifier' in name and 'bias' in name:
                param.data.fill_(0)
            elif 'gate' in name:
                param.data.fill_(1)


    def forward(self, x):
        features = self.features(x)
        out = F.relu(features, inplace=True)
        out = F.avg_pool2d(out, kernel_size=self.avgpool_size, stride=1).view(features.size(0), -1)
        out = self.classifier(out)
        return out


    def set_gate(self, gate_sets):
        for name, param in self.named_parameters():
            if 'gate' in name:
                param.data.fill_(0)

        for i, gate_set in enumerate(gate_sets):
            for name, param in self.named_parameters():
                if 'denseblock{}'.format(i) in name:
                    if 'grg' in name:
                        param.data[:, :gate_set[0], :, :] = 1
                    elif 'bg' in name:
                        param.data[:, :gate_set[1], :, :] = 1
                    elif 'lg' in name:
                        param.data.fill_(int(i<gate_set[2]))

        self.gate_sets = gate_sets
        print(self.gate_sets)


    def __get_param(self):
        
        def get_num(bidx, lidx):
            if lidx <= self.gate_sets[bidx][2]+1:
                return 0
            return lidx - self.gate_sets[bidx][2] - 1

        total_param = 0
        conv_param = []
        bn_param = []
        mask_size = self.arch_sets - self.gate_sets
        redundant_gate_from_previous_block = 0

        for name, m in self.named_modules():
            
            if 'denseblock' in name:
                name = name.split('.')
                if len(name) <= 2:
                    continue

                block_name = name[1]
                layer_name = name[2]
                block_idx = int(re.findall(r"\d+", block_name)[0]) - 1
                layer_idx = int(re.findall(r"\d+", layer_name)[0])
                mask_layer_num = get_num(block_idx, layer_idx)

                if isinstance(m, nn.Conv2d):
                    if 'conv1' in name:
                        param = m.kernel_size[0] * m.kernel_size[1] * \
                            (m.in_channels - redundant_gate_from_previous_block - \
                            (layer_idx-1) * mask_size[block_idx][0] - \
                            mask_layer_num * self.gate_sets[block_idx][0]) * \
                            self.gate_sets[block_idx][1]
                    else: #conv2
                        param = m.kernel_size[0] * m.kernel_size[1] * \
                            self.gate_sets[block_idx][1] * \
                            self.gate_sets[block_idx][0]
                    total_param += param
                    conv_param.append(param)

                elif isinstance(m, nn.BatchNorm2d):
                    if 'norm1' in name:
                        param = (m.num_features - redundant_gate_from_previous_block - \
                            (layer_idx-1) * mask_size[block_idx][0] - \
                            mask_layer_num * self.gate_sets[block_idx][0]) * 2
                    else:#norm2
                        param = self.gate_sets[block_idx][1] * 2
                    total_param += param
                    bn_param.append(param)

            elif 'transition' in name:
                name = name.split('.')
                if len(name) < 3:
                    continue
                else:
                    trans_name = name[1]
                    block_idx = int(re.findall(r"\d+", trans_name)[0]) - 1
                    mask_layer_num = get_num(block_idx, layer_idx+1)

                if isinstance(m, nn.BatchNorm2d):
                    redundant_gate_from_previous_block += (layer_idx * mask_size[block_idx][0] + \
                        mask_layer_num * self.gate_sets[block_idx][0])
                    param = (m.num_features - redundant_gate_from_previous_block) * 2
                    total_param += param
                    bn_param.append(param)

                elif isinstance(m, nn.Conv2d):
                    param = int(m.kernel_size[0] * m.kernel_size[1] * \
                            (m.in_channels - redundant_gate_from_previous_block) ** 2 * self.compression)
                    total_param += param
                    conv_param.append(param)
                    redundant_gate_from_previous_block = int(redundant_gate_from_previous_block * self.compression) 

            elif 'conv' in name:
                param = m.kernel_size[0] * m.kernel_size[1] * \
                                m.in_channels * m.out_channels
                conv_param.append(param)
                total_param += param

            elif 'norm' in name:
                if 'final' in name:
                    param = (m.num_features - layer_idx * mask_size[block_idx][0] - \
                        mask_layer_num * self.gate_sets[block_idx][0]) * 2
                else:
                    param = m.num_features * 2
                total_param += param
                bn_param.append(param)

            elif 'classifier' in name:
                total_param += m.out_features *  m.in_features

        return total_param, conv_param, bn_param
    

    def cost(self):
        dummy = torch.randn(1, 3, self.img_size, self.img_size).to(self.device)
        fmap_size = []
        handler_collection = []

        def fmap_size_hook(m, input, output):
            # if isinstance(input, tuple):
            #     input = input[0]
            fmap_size.append(output.size(2))

        def add_hooks(m):
            if len(list(m.children())) > 0:
                return

            if isinstance(m, nn.Conv2d):
                handler = m.register_forward_hook(fmap_size_hook)
                handler_collection.append(handler)

        total_ops = 0
        training = self.training
        self.eval()
        self.apply(add_hooks)

        with torch.no_grad():
            self(dummy)

        fmap_size.append(fmap_size[-1])

        total_param, conv_param, bn_param = self.__get_param()

        i = 0
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                out_elem = fmap_size[i] ** 2
                total_ops += out_elem * conv_param[i]
                if i > 0:
                    i += 1
            elif isinstance(m, nn.BatchNorm2d):
                total_ops += fmap_size[i] ** 2 * bn_param[i]
            elif isinstance(m, nn.ReLU):
                total_ops += fmap_size[i] ** 2 * bn_param[i] // 2
            elif isinstance(m, nn.MaxPool2d):
                total_ops += fmap_size[i] ** 2 * bn_param[i] // 2
                if i == 0: i += 1
            elif isinstance(m, nn.AvgPool2d):
                #transition layer
                total_ops += int(fmap_size[i-1] ** 2 * bn_param[i-1] // 2 * self.compression)
            elif isinstance(m, nn.Linear):
                total_ops += (2*m.in_features-1) * m.out_features

        self.train(training)
        for handler in handler_collection:
            handler.remove()

        return total_param, total_ops

    def to(self, *args, **kwargs):
        device, dtype, non_blocking = torch._C._nn._parse_to(*args, **kwargs)
        
        self.device = device

        if dtype is not None:
            if not dtype.is_floating_point:
                raise TypeError('nn.Module.to only accepts floating point '
                                'dtypes, but got desired dtype={}'.format(dtype))

        def convert(t):
            return t.to(device, dtype if t.is_floating_point() else None, non_blocking)

        return self._apply(convert)
# if __name__ == "__main__":
#     def cf(num, format="%.2f"):
#         if num > 1e12:
#             return format % (num / 1e12) + "T"
#         if num > 1e9:
#             return format % (num / 1e9) + "G"
#         if num > 1e6:
#             return format % (num / 1e6) + "M"
#         if num > 1e3:
#             return format % (num / 1e3) + "K"


#     net = densenet121()
#     # for n, p in net.named_parameters():
#     #     print(n, p.size())
#     # for m in net.children():
#     #     print(m)
   
#     gate_sets = np.array([[16, 128, 2],[32,128,6],[20,128,12],[32,128,16]])
#     net.set_gate(gate_sets)

#     p, f = net.cost()
#     print(cf(p), cf(f))