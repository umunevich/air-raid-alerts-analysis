"""Tests for baselines on processed training matrix."""

import pandas as pd

from air_raid_alerts.models.baselines import fit_baselines, label_horizons, predict_baselines
from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.pipeline import build_region_dataset
from helpers import sample_vadimkin_path


def test_fit_baselines_on_region_dataset(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    _intervals, _origins, _features, training_matrix, _manifest = build_region_dataset(
        events, "kyiv_city"
    )

    horizons = label_horizons(training_matrix)
    assert horizons == list(range(1, 25))

    # Fixture spans only the test window; fit on all rows to exercise the pipeline join.
    fitted = fit_baselines(
        training_matrix,
        horizons=horizons[:3],
        fit_mask=pd.Series(True, index=training_matrix.index),
    )
    preds = predict_baselines(fitted, training_matrix)

    assert len(preds) == len(training_matrix)
    assert preds.min().min() >= 0.0
    assert preds.max().max() <= 1.0
