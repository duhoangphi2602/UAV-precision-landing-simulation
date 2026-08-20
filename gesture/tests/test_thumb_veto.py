"""Unit gates for the bounded AUTO_LAND thumb-extension veto."""

import numpy as np
import pytest

from gesture.thumb_veto import (
    ALLOWED,
    REJECTED_BY_THUMB_VETO,
    derive_train_only_threshold,
    thumb_extension_components,
    thumb_extension_score,
    thumb_veto_status,
)


def canonical_thumb(ip_y: float, tip_y: float, tip_x: float = 1.0) -> np.ndarray:
    points = np.zeros((21, 3), dtype=np.float64)
    points[2] = (0.0, 0.0, 0.0)
    points[3] = (0.5, ip_y, 0.0)
    points[4] = (tip_x, tip_y, 0.0)
    points[5] = (0.0, -1.0, 0.0)
    points[9] = (0.0, -1.0, 0.0)
    points[13] = (0.0, -1.0, 0.0)
    points[17] = (0.0, -1.0, 0.0)
    return points.reshape(63)


def test_thumb_score_is_straightness_times_palm_relative_reach():
    feature = canonical_thumb(ip_y=0.0, tip_y=0.0)
    straightness, reach = thumb_extension_components(feature)
    assert straightness == pytest.approx(1.0)
    assert thumb_extension_score(feature) == pytest.approx(straightness * reach)


def test_threshold_is_train_only_order_statistic_with_required_retention():
    features = np.stack(
        [canonical_thumb(0.0, 0.0, tip_x=value) for value in range(1, 11)]
    )
    threshold = derive_train_only_threshold(features, minimum_retention=0.8)
    scores = sorted(thumb_extension_score(row) for row in features)
    assert threshold.value == pytest.approx(scores[2])
    assert threshold.required_allowed_samples == 8
    assert threshold.observed_allowed_samples == 8
    assert threshold.to_dict()["fit_scope"] == "TRAIN_FOLD_ONLY"


def test_veto_applies_only_to_auto_land_and_never_relabels():
    assert thumb_veto_status("AUTO_LAND", 0.4, 0.5) == REJECTED_BY_THUMB_VETO
    assert thumb_veto_status("AUTO_LAND", 0.5, 0.5) == ALLOWED
    assert thumb_veto_status("RIGHT", 0.1, 0.5) == ALLOWED


def test_thumb_rule_rejects_malformed_or_degenerate_geometry():
    with pytest.raises(ValueError, match="63D"):
        thumb_extension_score(np.zeros(62))
    with pytest.raises(ValueError, match="degenerate"):
        thumb_extension_score(np.zeros(63))
