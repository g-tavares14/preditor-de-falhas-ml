"""Fórmulas de X a partir de PingSample, sem JSON do Atlas."""

import pytest

from fakes import sample
from preditor_de_falhas_ml.domain.ping import FEATURE_COLUMNS, features_from_sample


def test_feature_columns_are_the_memo_vector():
    assert FEATURE_COLUMNS == ("latency_ms", "loss_pct", "jitter_rtt_ms")


def test_latency_loss_jitter_from_three_replies():
    features = features_from_sample(sample([10, 14, 12])).features
    assert features.as_dict() == {
        "latency_ms": 12.0,
        "loss_pct": 0.0,
        "jitter_rtt_ms": 3.0,
    }


@pytest.mark.parametrize(
    ("probe_id", "timestamp", "rtts", "latency", "jitter"),
    [
        (
            1000173,
            1788882988,
            [19.483448, 19.38372, 19.369888, 19.463916],
            19.425243,
            0.069196,
        ),
        (
            1016739,
            1788882989,
            [4.222306, 2.863131, 3.225258, 3.114455],
            3.3562875,
            0.6107016666666666,
        ),
    ],
)
def test_measurement_209319472_values(probe_id, timestamp, rtts, latency, jitter):
    observation = features_from_sample(sample(rtts, prb=probe_id, ts=timestamp))
    assert observation.key.probe_id.value == probe_id
    assert observation.features.latency_ms == pytest.approx(latency)
    assert observation.features.loss_pct == 0.0
    assert observation.features.jitter_rtt_ms == pytest.approx(jitter)


@pytest.mark.parametrize("missing", ["*", "Network unreachable"])
def test_jitter_does_not_bridge_missing_packets(missing):
    features = features_from_sample(sample([10, 14, missing, 100, 98])).features
    assert features.latency_ms == 55.5
    assert features.loss_pct == 20.0
    assert features.jitter_rtt_ms == 3.0


@pytest.mark.parametrize(
    ("rtts", "latency", "loss", "jitter"),
    [
        (["*"] * 3, None, 100.0, None),
        (["*", 10, "*"], 10.0, 200 / 3, None),
        ([10, "*", 20], 15.0, 100 / 3, None),
        ([0, 0], 0.0, 0.0, 0.0),
        ([], None, None, None),
    ],
)
def test_missing_metrics_are_none_and_observed_zeros_remain_zero(
    rtts, latency, loss, jitter
):
    features = features_from_sample(sample(rtts)).features
    assert features.latency_ms == latency
    assert features.loss_pct == loss
    assert features.jitter_rtt_ms == jitter


def test_other_destination_and_ipv6_are_accepted():
    observation = features_from_sample(sample([10, 12], dst="1.1.1.1", af=6))
    assert observation.destination == "1.1.1.1"
    assert observation.address_family == 6
    assert observation.features.latency_ms == 11.0
