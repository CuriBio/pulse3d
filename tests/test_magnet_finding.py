# -*- coding: utf-8 -*-
from pulse3D import magnet_finding
from pulse3D import plate_recording,filter_magnet_positions
from pulse3D import MEMSIC_CENTER_OFFSET
from pulse3D import MEMSIC_FULL_SCALE,MEMSIC_MSB
from pulse3D import GAUSS_PER_MILLITESLA
from pulse3D import REFERENCE_SENSOR_READINGS, TIME_INDICES,TIME_OFFSETS
from pulse3D import TISSUE_SENSOR_READINGS,WELL_IDX_TO_MODULE_ID,MODULE_ID_TO_WELL_IDX
from pulse3D import PlateRecording
from pulse3D.plate_recording import _load_files
# from pulse3D import WellFile
from pulse3D import MantarrayH5FileCreator
from h5py import File
import numpy as np
import pytest

from pulse3D.transforms import calculate_force_from_displacement


# def test_data_validity():
#     processed_data, processed_timestamps = magnet_finding.processData("tests/magnet_finding/Durability_Test_11162021_data_Baseline")
#     # convert_to_h5(processed_data, processed_timestamps)

#     recording_name = "Durability_Test_11162021_data_Baseline"
#     # for well_idx in range(24):
#     #     module_id = WELL_IDX_TO_MODULE_ID[well_idx]
#     #     file_path = f"tests/magnet_finding/{recording_name}/{recording_name}__module_{module_id}.h5"

#     #     with File(file_path, "r") as well_file:
#     #         adjusted_time_indices = -well_file[TIME_OFFSETS][:] + well_file[TIME_INDICES][:]
#     #     np.testing.assert_array_almost_equal(
#     #         adjusted_time_indices.astype(np.float64), processed_timestamps[module_id - 1, :, :], err_msg=f"Well: {well_idx}"
#     #     )
#     loaded_data = load_h5_folder_as_array(recording_name)
#     loaded_data_mt = (
#         (loaded_data - MEMSIC_CENTER_OFFSET)
#         * MEMSIC_FULL_SCALE
#         / MEMSIC_MSB
#         / GAUSS_PER_MILLITESLA
#     )
#     np.testing.assert_array_almost_equal(
#         loaded_data_mt, processed_data
#     )


def load_h5_folder_as_array(recording_name):
    # TODO Tanner (12/3/21): This should be in src
    plate_data_array = None
    for module_id in range(1, 25):
        file_path = f"tests/magnet_finding/{recording_name}/{recording_name}__module_{module_id}.h5"

        with File(file_path, "r") as well_file:
            tissue_data = well_file[TISSUE_SENSOR_READINGS][:]
        if plate_data_array is None:
            num_samples = tissue_data.shape[-1]
            plate_data_array = np.empty((24, 3, 3, num_samples))
        reshaped_data = tissue_data.reshape((3, 3, num_samples))
        plate_data_array[module_id - 1, :, :, :] = reshaped_data
    return plate_data_array


@pytest.mark.slow
def test_get_positions__returns_expected_values():
    loaded_data = load_h5_folder_as_array("Durability_Test_11162021_data_90min")
    loaded_data_mt = (
        (loaded_data - MEMSIC_CENTER_OFFSET)
        * MEMSIC_FULL_SCALE
        / MEMSIC_MSB
        / GAUSS_PER_MILLITESLA
    )
    outputs = magnet_finding.get_positions(loaded_data_mt[:, :, :, 2:102])

    output_file = File(
        "tests/magnet_finding/magnet_finding_output_100pts.h5",
        "r",
        libver="latest",
    )

    acc = {output_name: -1 for output_name in outputs.keys()}
    for output_name, output in outputs.items():
        for decimal in range(0, 14):
            try:
                np.testing.assert_array_almost_equal(
                    output,
                    output_file[output_name],
                    decimal=decimal,
                    err_msg=f"output_name"
                )
            except AssertionError:
                acc[output_name] = decimal - 1
                break
    print(acc)
    assert all(val >= 3 for val in acc.values())


@pytest.mark.slow
def test_PlateRecording__creates_correct_displacement_and_force_data_for_beta_2_files(mocker):
    num_points_to_test = 100

    def load_files_se(*args):
        well_files = _load_files(*args)
        for well_file in well_files:
            well_file[TIME_INDICES] = well_file[TIME_INDICES][:num_points_to_test]
            well_file[TIME_OFFSETS] = well_file[TIME_OFFSETS][:, :num_points_to_test]
            well_file[TISSUE_SENSOR_READINGS] = well_file[TISSUE_SENSOR_READINGS][:, :num_points_to_test]
            well_file[REFERENCE_SENSOR_READINGS] = well_file[REFERENCE_SENSOR_READINGS][:, :num_points_to_test]
        return well_files

    mocker.patch.object(
        plate_recording,
        "_load_files",
        autospec=True,
        side_effect=load_files_se
    )

    # mock this so data doesn't actually get filtered and is easier to test
    mocked_filter = mocker.patch.object(
        magnet_finding,
        "filter_magnet_positions",
        autospec=True,
        side_effect=lambda x: x,
    )

    pr = PlateRecording("tests/magnet_finding/MA200440001__2020_02_09_190359__with_calibration_recordings.zip")
    assert mocked_filter.call_count == magnet_finding.NUM_PARAMS

    output_file = File(
        "tests/magnet_finding/magnet_finding_output_100pts__baseline_removed.h5",
        "r",
        libver="latest",
    )

    for well_idx, well_file in enumerate(pr.wells):
        # test displacement
        module_id = WELL_IDX_TO_MODULE_ID[well_idx]
        expected_displacement = np.array(
            [well_file[TIME_INDICES], output_file["X"][:, module_id - 1]]
        )
        # Tanner (12/7/21): iterating through different decimal precision here since the precision is different for each well, but 
        np.testing.assert_array_almost_equal(
            well_file.displacement,
            expected_displacement,
            decimal=5,
            err_msg=f"{well_idx}",
        )
        # test force
        expected_force = calculate_force_from_displacement(well_file.displacement)
        np.testing.assert_array_almost_equal(
            well_file.force,
            expected_force,
            err_msg=f"{well_idx}",
        )


# def test_100_pts_og():
#     baseline, _ = magnet_finding.processData("tests/magnet_finding/Durability_Test_11162021_data_Baseline")
#     processed_data, _ = magnet_finding.processData("tests/magnet_finding/Durability_Test_11162021_data_90min")
#     outputs = magnet_finding.getPositions(processed_data[:, :, :, :100] - baseline[:, :, :, :100])
#     save_outputs(outputs)


def convert_to_h5(processed_data, processed_time_indices):
    for module_id in range(1, 25):
        print(module_id)
        time_indices = processed_time_indices[module_id - 1, :, :]
        data = processed_data[module_id - 1, :, :, :]

        num_sensors_active = 3
        num_axes_active = 3
        num_channels_enabled = num_sensors_active  * num_axes_active
        max_data_len = data.shape[-1]
        data_shape = (num_channels_enabled, max_data_len)
        maxshape = (num_channels_enabled, max_data_len)
        data_dtype = "uint16"

        this_file = MantarrayH5FileCreator(
            f"tests/magnet_finding/Durability_Test_11162021_data_Baseline/Durability_Test_11162021_data_Baseline__module_{module_id}.h5",
            file_format_version="1.0.0"
        )
        this_file.create_dataset(
            TIME_INDICES,
            (max_data_len,),
            maxshape=(max_data_len,),
            dtype="uint64",
            chunks=True,
        )
        this_file.create_dataset(
            TIME_OFFSETS,
            (num_sensors_active, max_data_len),
            maxshape=(num_sensors_active, max_data_len),
            dtype="uint16",
            chunks=True,
        )
        for idx in range(time_indices.shape[-1]):
            paired_time_indices = time_indices[:, idx]
            max_time_index = max(paired_time_indices)
            time_offsets = max_time_index - paired_time_indices
            this_file[TIME_INDICES][idx] = max_time_index
            this_file[TIME_OFFSETS][:, idx] = time_offsets
        this_file.create_dataset(
            REFERENCE_SENSOR_READINGS,
            data_shape,
            maxshape=maxshape,
            dtype=data_dtype,
            chunks=True,
        )
        this_file[REFERENCE_SENSOR_READINGS][:] = np.zeros(data_shape)
        this_file.create_dataset(
            TISSUE_SENSOR_READINGS,
            data_shape,
            maxshape=maxshape,
            dtype=data_dtype,
            chunks=True,
        )
        for sensor_idx in range(num_sensors_active):
            for axis_idx in range(num_axes_active):
                channel_idx = sensor_idx * 3 + axis_idx
                this_file[TISSUE_SENSOR_READINGS][channel_idx, :] = data[sensor_idx, axis_idx, :]
        this_file.close()


def save_outputs(outputs):
    output_file = File(
        "tests/magnet_finding/magnet_finding_output_100pts__baseline_removed.h5",
        "w",
        libver="latest",
        userblock_size=512,
    )

    output_names = ["X", "Y", "Z", "THETA", "PHI", "REMN"]
    for i, name in enumerate(output_names):
        output_file.create_dataset(
            name,
            outputs[i].shape,
            maxshape=outputs[i].shape,
            dtype="float64",
            chunks=True,
        )
        output_file[name][:] = outputs[i]