from __future__ import absolute_import, division, print_function

import dask
from dask.array.blaze import *
from into import discover, convert, into
from collections import Iterable
from toolz import concat
from operator import getitem


def eq(a, b):
    c = a == b
    if isinstance(c, np.ndarray):
        c = c.all()
    return c


nx = np.arange(600).reshape((20, 30))
dx = convert(Array, nx, blockshape=(4, 5))
sx = symbol('x', discover(dx))

ny = np.arange(600).reshape((30, 20))
dy = convert(Array, ny, blockshape=(5, 4))
sy = symbol('y', discover(dy))

na = np.arange(20)
da = convert(Array, na, blockshape=(4,))
sa = symbol('a', discover(da))

nb = np.arange(30).reshape((30, 1))
db = convert(Array, nb, blockshape=(5, 1))
sb = symbol('b', discover(db))

dask_ns = {sx: dx, sy: dy, sa: da, sb: db}
numpy_ns = {sx: nx, sy: ny, sa: na, sb: nb}


def test_compute():
    for expr in [2*sx + 1,
                 sx.sum(axis=0), sx.mean(axis=0),
                 sx + sx, sx.T, sx.T + sy,
                 sx.dot(sy), sy.dot(sx),
                 sx.sum(),
                 sx - sx.sum(),
                 sx.dot(sx.T),
                 sx.sum(axis=1),
                 sy + sa,
                 sy + sb,
                 sx[3:17], sx[3:10, 10:25:2] + 1, sx[:5, 10],
                 sx[0, 0]
                ]:
        result = compute(expr, dask_ns)
        expected = compute(expr, numpy_ns)
        assert isinstance(result, Array)
        if expr.dshape.shape:
            result2 = into(np.ndarray, result)
        else:
            result2 = into(float, result)
        assert eq(result2, expected)


def test_elemwise_broadcasting():
    arr = compute(sy + sb, dask_ns)
    expected =  [[(arr.name, i, j) for j in range(5)]
                                   for i in range(6)]
    assert arr.keys() == expected


def test_ragged_blockdims():
    dsk = {('x', 0, 0): np.ones((2, 2)),
           ('x', 0, 1): np.ones((2, 3)),
           ('x', 1, 0): np.ones((5, 2)),
           ('x', 1, 1): np.ones((5, 3))}

    a = Array(dsk, 'x', shape=(7, 5), blockdims=[(2, 5), (2, 3)])
    s = symbol('s', '7 * 5 * int')

    assert compute(s.sum(axis=0), a).blockdims == ((2, 3),)
    assert compute(s.sum(axis=1), a).blockdims == ((2, 5),)

    assert compute(s + 1, a).blockdims == a.blockdims


def test_slicing_with_singleton_dimensions():
    arr = compute(sx[5:15, 12], dx)
    x = dx.name
    y = arr.name
    assert arr.dask[(y, 0)] == (getitem, (x, 1, 2), (slice(1, 4, 1), 2))
    assert arr.dask[(y, 1)] == (getitem, (x, 2, 2), (slice(0, 4, 1), 2))
    assert arr.dask[(y, 2)] == (getitem, (x, 3, 2), (slice(0, 3, 1), 2))
    assert all(len(k) == 2 for k in arr.keys())
