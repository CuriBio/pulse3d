# -*- coding: utf-8 -*-
"""General utility/helpers."""
import json
import logging
import math
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from uuid import UUID

from nptyping import NDArray

from .constants import CONTRACTION_TIME_UUID
from .constants import RELAXATION_TIME_UUID
from .constants import TIME_DIFFERENCE_UUID
from .constants import WIDTH_FALLING_COORDS_UUID
from .constants import WIDTH_RISING_COORDS_UUID
from .constants import WIDTH_UUID

logger = logging.getLogger(__name__)


def truncate_float(value: float, digits: int) -> float:
    if digits < 1:
        raise ValueError("If truncating all decimals off of a float, just use builtin int() instead")
    # from https://stackoverflow.com/questions/8595973/truncate-to-three-decimals-in-python
    stepper = 10.0 ** digits
    return math.trunc(stepper * value) / stepper


def truncate(
    source_series: NDArray[(1, Any), float],
    lower_bound: Union[int, float],
    upper_bound: Union[int, float],
) -> Tuple[int, int]:
    """Match bounding indices of source time-series with reference time-series.

    Args:
        source_series (NDArray): time-series to truncate
        lower_bound/upper_bound (float): bounding times of a reference time-series

    Returns:
        first_idx (int): index corresponding to lower bound of source time-series
        last_idx (int): index corresponding to upper bound of source time-series
    """
    first_idx, last_idx = 0, len(source_series) - 1
    while upper_bound < source_series[last_idx]:
        last_idx -= 1

    # left-truncation
    while lower_bound > source_series[first_idx]:
        first_idx += 1

    return first_idx, last_idx


def serialize_main_dict(per_twitch_dict: Dict[int, Any], metrics_to_create: Iterable[UUID]) -> Dict[str, Any]:
    """Serialize a per-twitch-dict for saving as JSON.

    Args:
        per_twitch_dict: dictionary of per-twitch values as generated by `mantarray_waveform_analysis.peak_detection.data_metrics`
        metrics_to_create: list of UUID metrics

    Returns:
        serialized: dictionary of serialized per-twitch values
    """

    def add_metric(twitch: int, metric: UUID) -> Union[str, Dict[str, Any]]:
        # get current per_twitch_metric dictionary
        temp_metric_dict = per_twitch_dict[twitch][metric]

        if metric == TIME_DIFFERENCE_UUID:
            time_diff: Dict[str, Dict[str, str]] = {str(perc): dict() for perc in range(10, 95, 5)}

            for twitch_width_perc in range(10, 95, 5):
                temp_width_dict = temp_metric_dict[twitch_width_perc]
                time_diff[str(twitch_width_perc)] = dict(
                    zip(
                        map(str, temp_width_dict.keys()),
                        map(str, [temp_width_dict[submetric] for submetric in temp_width_dict.keys()]),
                    )
                )

            return time_diff

        if metric == WIDTH_UUID:
            widths: Dict[str, Dict[str, Any]] = {str(perc): dict() for perc in range(10, 95, 5)}

            for twitch_width_perc in range(10, 95, 5):
                temp_width_dict = temp_metric_dict[twitch_width_perc]
                per_perc_width_dict: Dict[str, Union[str, List[str]]]
                per_perc_width_dict = {str(key): list() for key in temp_width_dict.keys()}

                for key, value in temp_width_dict.items():
                    if key in [WIDTH_RISING_COORDS_UUID, WIDTH_FALLING_COORDS_UUID]:
                        per_perc_width_dict[str(key)] = list(map(str, value))
                    else:
                        per_perc_width_dict[str(key)] = str(value)

                widths[str(twitch_width_perc)] = per_perc_width_dict
            return widths

        return str(per_twitch_dict[twitch][metric])

    serialized: Dict[str, Any] = {
        str(twitch): {str(metric): add_metric(twitch, metric) for metric in metrics_to_create}
        for twitch in per_twitch_dict.keys()
    }
    return serialized


def deserialize_main_dict(json_file: str, metrics_to_create: Iterable[UUID]) -> Dict[int, Any]:
    """De-serialize a per-twitch-dict after loading from JSON.

    Args:
        json_file: saved serialized dictionary
        metrics_to_create: list of UUID metrics

    Returns:
        serialized: dictionary of de-serialized per-twitch values
    """
    with open(json_file, "r") as file_object:
        serialized = json.load(file_object)

    twitches = serialized.keys()
    deserialized: Dict[int, Dict[UUID, Any]] = {int(twitch): {} for twitch in twitches}

    def add_metric(twitch: int, metric: UUID) -> Union[float, Dict[int, Any]]:
        twitch_dict = serialized[twitch]

        # get dictionary associated with specific metrics
        temp_metric_dict = twitch_dict[str(metric)]

        if metric == TIME_DIFFERENCE_UUID:
            time_diffs: Dict[int, Dict[UUID, float]]
            time_diffs = {perc: dict() for perc in range(10, 95, 5)}

            # iterate over twitch_widths
            for twitch_width_perc in range(10, 95, 5):
                # get dictionary associated with twitch width
                temp_width_dict = temp_metric_dict[str(twitch_width_perc)]

                keys = map(UUID, temp_width_dict.keys())
                values = map(float, [temp_width_dict[submetric] for submetric in temp_width_dict.keys()])
                time_diffs[twitch_width_perc] = dict(zip(keys, values))

            return time_diffs

        if metric == WIDTH_UUID:
            widths: Dict[int, Dict[UUID, Union[float, List[float]]]]
            widths = {perc: dict() for perc in range(10, 95, 5)}

            # iterate over twitch_widths
            for twitch_width_perc in range(10, 95, 5):
                # get dictionary associated with twitch width
                temp_width_dict = temp_metric_dict[str(twitch_width_perc)]
                per_perc_width_dict: Dict[UUID, Any]
                per_perc_width_dict = {UUID(key): tuple() for key in temp_width_dict.keys()}

                for key, value in temp_width_dict.items():
                    if key in map(str, [WIDTH_RISING_COORDS_UUID, WIDTH_FALLING_COORDS_UUID]):
                        per_perc_width_dict[UUID(key)] = tuple(map(float, value))
                    else:
                        per_perc_width_dict[UUID(key)] = float(value)

                widths[twitch_width_perc] = per_perc_width_dict

            return widths

        return float(temp_metric_dict)

    # iterate over twitches
    for twitch in serialized.keys():
        # iterate over metrics
        for metric in metrics_to_create:
            deserialized[int(twitch)][metric] = add_metric(twitch, metric)
    return deserialized


def serialize_aggregate_dict(
    aggregate_dict: Dict[UUID, Any], metrics_to_create: Iterable[UUID]
) -> Dict[str, Any]:
    """Serialize a per-twitch-dict for saving as JSON.

    Args:
        per_twitch_dict: dictionary of per-twitch values as generated by `mantarray_waveform_analysis.peak_detection.data_metrics`
        metrics_to_create: list of UUID metrics

    Returns:
        serialized: dictionary of serialized per-twitch values
    """
    estimates = ["n", "mean", "std", "min", "max"]

    def by_twitch_width(temp_metric: UUID) -> Dict[str, Any]:
        temp_metric_dict = aggregate_dict[temp_metric]
        by_width: Dict[str, Dict[str, Any]]
        by_width = {
            str(perc): {estimate: str(temp_metric_dict[perc][estimate]) for estimate in estimates}
            for perc in range(10, 95, 5)
        }

        return by_width

    serialized = {}
    for metric in metrics_to_create:
        if metric == TIME_DIFFERENCE_UUID:
            for sub_metric in [RELAXATION_TIME_UUID, CONTRACTION_TIME_UUID]:
                serialized[str(sub_metric)] = by_twitch_width(sub_metric)
        elif metric == WIDTH_UUID:
            serialized[str(metric)] = by_twitch_width(metric)
        else:
            temp = {str(estimate): str(aggregate_dict[metric][estimate]) for estimate in estimates}
            serialized[str(metric)] = temp

    return serialized


def deserialize_aggregate_dict(json_file: str, metrics_to_create: Iterable[UUID]) -> Dict[UUID, Any]:
    """De-serialize an aggreagate-dict after loading from JSON.

    Args:
        json_file: saved serialized dictionary
        metrics_to_create: list of UUID metrics

    Returns:
        serialized: dictionary of de-serialized aggregate metrics
    """
    deserialized: Dict[UUID, Dict[Union[str, int], Any]] = dict()

    with open(json_file, "r") as file_object:
        serialized = json.load(file_object)

    estimates = ["n", "mean", "std", "min", "max"]

    # python can't cast "None" string to None, so we add this
    def str_to_float(input_string: str) -> Optional[float]:
        return None if input_string == "None" else float(input_string)

    def by_twitch_width(temp_metric: UUID) -> Dict[Union[str, int], Any]:
        temp_metric_dict = serialized[str(temp_metric)]
        by_width: Dict[Union[str, int], Any]
        by_width = {perc: {str(estimate): None for estimate in estimates} for perc in range(10, 95, 5)}

        for twitch_width_perc in range(10, 95, 5):
            for estimate in estimates:
                by_width[twitch_width_perc][str(estimate)] = float(
                    temp_metric_dict[str(twitch_width_perc)][str(estimate)]
                )

        return by_width

    for metric in metrics_to_create:
        if metric == TIME_DIFFERENCE_UUID:
            for sub_metric in [RELAXATION_TIME_UUID, CONTRACTION_TIME_UUID]:
                deserialized[sub_metric] = by_twitch_width(sub_metric)
        elif metric == WIDTH_UUID:
            deserialized[metric] = by_twitch_width(metric)
        else:
            temp: Dict[Union[str, int], Any]
            temp = {estimate: str_to_float(serialized[str(metric)][(estimate)]) for estimate in estimates}
            deserialized[metric] = temp

    return deserialized


def xl_col_to_name(col, col_abs=False):
    """Convert a zero indexed column cell reference to a string.

    Args:
       col:     The cell column. Int.
       col_abs: Optional flag to make the column absolute. Bool.

    Returns:
        Column style string.
    """
    col_num = col
    if col_num < 0:
        raise ValueError("col arg must >= 0")

    col_num += 1  # Change to 1-index.
    col_str = ""
    col_abs = "$" if col_abs else ""

    while col_num:
        # Set remainder from 1 .. 26
        remainder = col_num % 26
        if remainder == 0:
            remainder = 26
        # Convert the remainder to a character.
        col_letter = chr(ord("A") + remainder - 1)
        # Accumulate the column letters, right to left.
        col_str = col_letter + col_str
        # Get the next order of magnitude.
        col_num = int((col_num - 1) / 26)

    return col_abs + col_str
