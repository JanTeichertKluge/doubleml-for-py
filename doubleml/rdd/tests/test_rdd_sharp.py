"""
Dummy test using fixed learner for sharp data
"""
import pytest
import numpy as np


@pytest.fixture(scope='module',
                params=[-0.2, 0.0, 0.4])
def cutoff(request):
    return request.param


@pytest.fixture(scope='module',
                params=[0.05, 0.1])
def alpha(request):
    return request.param


@pytest.fixture(scope='module',
                params=[1, 3])
def n_rep(request):
    return request.param


@pytest.fixture(scope='module',
                params=[1, 2])
def p(request):
    return request.param


@pytest.fixture(scope='module')
def data(rdd_sharp_data, cutoff):
    return rdd_sharp_data(cutoff)


@pytest.fixture(scope='module')
def data_zero(rdd_sharp_data):
    return rdd_sharp_data(0.0)


@pytest.fixture(scope='module')
def predict_placebo(predict_dummy, data_zero, cutoff, alpha, p, n_rep):
    return predict_dummy(
        data_zero, cutoff=cutoff, alpha=alpha, n_rep=n_rep, p=p
    )


@pytest.fixture(scope='module')
def predict_nonplacebo(predict_dummy, data, cutoff, alpha, p, n_rep):
    return predict_dummy(
        data, cutoff=cutoff, alpha=alpha, n_rep=n_rep, p=p
    )


@pytest.mark.ci
def test_rdd_placebo_coef(predict_placebo):
    reference, actual = predict_placebo
    assert np.allclose(actual['coef'], reference['coef'], rtol=1e-9, atol=1e-4)


@pytest.mark.ci
def test_rdd_nonplacebo_coef(predict_nonplacebo):
    reference, actual = predict_nonplacebo
    assert np.allclose(actual['coef'], reference['coef'], rtol=1e-9, atol=1e-4)


@pytest.mark.ci
def test_rdd_placebo_se(predict_placebo):
    reference, actual = predict_placebo
    assert np.allclose(actual['se'], reference['se'], rtol=1e-9, atol=1e-4)


@pytest.mark.ci
def test_rdd_nonplacebo_se(predict_nonplacebo):
    reference, actual = predict_nonplacebo
    assert np.allclose(actual['se'], reference['se'], rtol=1e-9, atol=1e-4)


@pytest.mark.ci
def test_rdd_placebo_ci(predict_placebo):
    reference, actual = predict_placebo
    assert np.allclose(actual['ci'], reference['ci'], rtol=1e-9, atol=1e-4)


@pytest.mark.ci
def test_rdd_nonplacebo_ci(predict_nonplacebo):
    reference, actual = predict_nonplacebo
    assert np.allclose(actual['ci'], reference['ci'], rtol=1e-9, atol=1e-4)
