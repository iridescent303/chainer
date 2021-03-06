import math
import unittest

import mock
import numpy
import six

import chainer
from chainer import cuda
from chainer import functions
from chainer import gradient_check
from chainer import testing
from chainer.testing import attr
from chainer.testing import condition


@testing.parameterize(
    {'shape': (8, 7), 'normalize': True},
    {'shape': (8, 7), 'normalize': False},
    {'shape': (8, 7), 'normalize': True, 'ignore_all': True},
    # too large shape causes int32 -> float64 issue
    {'shape': (65536, 1), 'normalize': False},
)
class TestSigmoidCrossEntropy(unittest.TestCase):

    def setUp(self):
        self.x = numpy.random.uniform(-1, 1, self.shape).astype(numpy.float32)
        if getattr(self, 'ignore_all', False):
            self.t = -numpy.ones(self.shape).astype(numpy.int32)
        else:
            self.t = numpy.random.randint(-1, 2,
                                          self.shape).astype(numpy.int32)
        self.gy = numpy.random.random(self.shape).astype(numpy.float32)

    def check_forward(self, x_data, t_data, use_cudnn='always'):
        x_val = chainer.Variable(x_data)
        t_val = chainer.Variable(t_data)
        with chainer.using_config('use_cudnn', use_cudnn):
            loss = functions.sigmoid_cross_entropy(x_val, t_val,
                                                   self.normalize)
        self.assertEqual(loss.data.shape, ())
        self.assertEqual(loss.data.dtype, numpy.float32)
        loss_value = float(cuda.to_cpu(loss.data))

        # Compute expected value
        loss_expect = 0
        non_ignore_count = 0
        for i in six.moves.range(self.x.shape[0]):
            for j in six.moves.range(self.x.shape[1]):
                xd, td = self.x[i, j], self.t[i, j]
                if td == -1:
                    continue
                loss_expect -= xd * (td - (xd >= 0)) \
                    - math.log(1 + math.exp(-numpy.abs(xd)))
                non_ignore_count += 1
        if non_ignore_count == 0:
            loss_expect = 0
        elif self.normalize:
            loss_expect /= non_ignore_count
        else:
            loss_expect /= self.t.shape[0]
        self.assertAlmostEqual(loss_expect, loss_value, places=5)

    def check_forward_no_reduction(self, x_data, t_data):
        x_val = chainer.Variable(x_data)
        t_val = chainer.Variable(t_data)
        loss = functions.sigmoid_cross_entropy(
            x_val, t_val, self.normalize, reduce='no')
        self.assertEqual(loss.data.shape, self.x.shape)
        self.assertEqual(loss.data.dtype, numpy.float32)
        loss_value = cuda.to_cpu(loss.data)

        # Compute expected value
        if not getattr(self, 'ignore_all', False):
            for i in six.moves.range(self.x.shape[0]):
                for j in six.moves.range(self.x.shape[1]):
                    xd, td = self.x[i, j], self.t[i, j]
                    if td == -1:
                        loss_expect = 0
                    else:
                        loss_expect = -(
                            xd * (td - (xd >= 0)) -
                            math.log(1 + math.exp(-numpy.abs(xd))))
                    self.assertAlmostEqual(
                        loss_expect, loss_value[i, j], places=5)

    @condition.retry(3)
    def test_forward_cpu(self):
        with chainer.using_config('use_cudnn', 'always'):
            self.check_forward(self.x, self.t)

    @condition.retry(3)
    def test_forward_no_reduction_cpu(self):
        with chainer.using_config('use_cudnn', 'always'):
            self.check_forward_no_reduction(self.x, self.t)

    @attr.gpu
    @condition.retry(3)
    def test_forward_gpu(self):
        with chainer.using_config('use_cudnn', 'always'):
            self.check_forward(cuda.to_gpu(self.x), cuda.to_gpu(self.t))

    @attr.gpu
    @condition.retry(3)
    def test_forward_no_reduction_gpu(self):
        with chainer.using_config('use_cudnn', 'always'):
            self.check_forward_no_reduction(
                cuda.to_gpu(self.x), cuda.to_gpu(self.t))

    @attr.gpu
    @condition.retry(3)
    def test_forward_gpu_no_cudnn(self):
        with chainer.using_config('use_cudnn', 'never'):
            self.check_forward(cuda.to_gpu(self.x), cuda.to_gpu(self.t))

    @attr.gpu
    @condition.retry(3)
    def test_forward_no_reduction_gpu_no_cudnn(self):
        with chainer.using_config('use_cudnn', 'never'):
            self.check_forward_no_reduction(
                cuda.to_gpu(self.x), cuda.to_gpu(self.t))

    def check_backward(self, x_data, t_data, y_grad):
        # Skip too large case. That requires a long time.
        if self.shape[0] == 65536:
            return

        gradient_check.check_backward(
            functions.SigmoidCrossEntropy(),
            (x_data, t_data), None, eps=1e-2)

    def check_backward_no_reduction(
            self, x_data, t_data, y_grad):
        # Skip too large case. That requires a long time.
        if self.shape[0] == 65536:
            return

        gradient_check.check_backward(
            functions.SigmoidCrossEntropy(reduce='no'),
            (x_data, t_data), y_grad, eps=1e-2)

    @condition.retry(3)
    def test_backward_cpu(self):
        with chainer.using_config('use_cudnn', 'never'):
            self.check_backward(self.x, self.t, self.gy)

    @condition.retry(3)
    def test_backward_no_reduction_cpu(self):
        with chainer.using_config('use_cudnn', 'never'):
            self.check_backward_no_reduction(self.x, self.t, self.gy)

    @attr.gpu
    @condition.retry(3)
    def test_backward_gpu(self):
        with chainer.using_config('use_cudnn', 'always'):
            self.check_backward(
                cuda.to_gpu(self.x), cuda.to_gpu(self.t), cuda.to_gpu(self.gy))

    @attr.gpu
    @condition.retry(3)
    def test_backward_no_reduction_gpu(self):
        with chainer.using_config('use_cudnn', 'always'):
            self.check_backward_no_reduction(
                cuda.to_gpu(self.x), cuda.to_gpu(self.t), cuda.to_gpu(self.gy))

    @attr.gpu
    @condition.retry(3)
    def test_backward_gpu_no_cudnn(self):
        with chainer.using_config('use_cudnn', 'never'):
            self.check_backward(
                cuda.to_gpu(self.x), cuda.to_gpu(self.t),
                cuda.to_gpu(self.gy))

    @attr.gpu
    @condition.retry(3)
    def test_backward_no_reduction_gpu_no_cudnn(self):
        with chainer.using_config('use_cudnn', 'never'):
            self.check_backward_no_reduction(
                cuda.to_gpu(self.x), cuda.to_gpu(self.t),
                cuda.to_gpu(self.gy))


@testing.parameterize(
    {'use_cudnn': 'always'},
    {'use_cudnn': 'auto'},
    {'use_cudnn': 'never'},
)
@attr.cudnn
class TestSigmoidCrossEntropyCudnnCall(unittest.TestCase):

    def setUp(self):
        self.x = cuda.cupy.random.uniform(-1, 1, (4, 3)).astype(numpy.float32)
        self.t = cuda.cupy.random.randint(0, 3, (4, 3)).astype(numpy.int32)
        with chainer.using_config('use_cudnn', self.use_cudnn):
            self.expect = chainer.should_use_cudnn('==always')

    def forward(self):
        x = chainer.Variable(self.x)
        t = chainer.Variable(self.t)
        return functions.sigmoid_cross_entropy(x, t)

    def test_call_cudnn_backward(self):
        with chainer.using_config('use_cudnn', self.use_cudnn):
            y = self.forward()
            patch = 'cupy.cudnn.cudnn.activationForward_v4'
            with mock.patch(patch) as func:
                y.backward()
                self.assertEqual(func.called, self.expect)

    # Note that SoftmaxCrossEntropy does not use cudnn on backward


testing.run_module(__name__, __file__)
