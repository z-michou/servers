from datetime import datetime

import numpy as np
import pytest

import labrad
import labrad.types as T
import labrad.util.hydrant as hydrant

# use the same path for all datasets in a given run of the tests in this module
_path = None

def _test_path():
    """Path where we'll put test datasets in the data vault"""
    global _path
    if _path is None:
        _path = ['test', datetime.utcnow().strftime('%Y%m%d')]
    return _path

def setup_dv(cxn):
    dv = cxn.data_vault
    dv.cd(_test_path(), True)
    return dv

@pytest.yield_fixture
def dv():
    with labrad.connect() as cxn:
        dv = setup_dv(cxn)
        yield dv

def test_create_dataset(dv):
    """Create a simple dataset, add some data and read it back"""
    _path, _name = dv.new('test', ['x', 'y'], ['z'])

    data = []
    for x in xrange(10):
        for y in xrange(10):
            data.append([x/10., y/10., x*y])

    for row in data:
        dv.add(row)

    stored = dv.get()
    assert np.equal(data, stored).all()

def test_read_dataset():
    """Create a simple dataset and read it back while still open and after closed"""
    data = []
    for x in xrange(10):
        for y in xrange(10):
            data.append([x/10., y/10., x*y])

    with labrad.connect() as cxn:
        dv = setup_dv(cxn)

        path, name = dv.new('test', ['x', 'y'], ['z'])

        for row in data:
            dv.add(row)

        # read in new connection while the dataset is still open
        with labrad.connect() as cxn2:
            dv2 = cxn2.data_vault
            dv2.cd(path)
            dv2.open(name)
            stored = dv2.get()
            assert np.equal(data, stored).all()

            # add more data and ensure that we get it
            dv.add([1, 1, 100])

            row = dv2.get()
            assert np.equal(row, [1, 1, 100]).all()

    # read in new connection after dataset has been closed
    with labrad.connect() as cxn:
        dv = cxn.data_vault
        dv.cd(path)
        dv.open(name)
        stored = dv.get(len(data)) # get only up to the last extra row
        assert np.equal(data, stored).all()


def test_parameters(dv):
    """Create a dataset with parameters"""
    dv.new('test', ['x', 'y'], ['z'])
    for i in xrange(100):
        t = hydrant.randType(noneOkay=False)
        a = hydrant.randValue(t)
        name = 'param{}'.format(i)
        dv.add_parameter(name, a)
        b = dv.get_parameter(name)
        sa, ta = T.flatten(a)
        sb, tb = T.flatten(b)
        assert ta == tb
        assert sa == sb

if __name__ == "__main__":
    pytest.main(['-v', __file__])
