# Copyright 2016-2020 The Van Valen Lab at the California Institute of
# Technology (Caltech), with support from the Paul Allen Family Foundation,
# Google, & National Institutes of Health (NIH) under Grant U24CA224309-01.
# All rights reserved.
#
# Licensed under a modified Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.github.com/vanvalenlab/caliban-toolbox/LICENSE
#
# The Work provided may be used for non-commercial academic purposes only.
# For any other use of the Work, including commercial use, please contact:
# vanvalenlab@gmail.com
#
# Neither the name of Caltech nor the names of its contributors may be used
# to endorse or promote products derived from this software without specific
# prior written permission.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
import os
import json
import pytest

import numpy as np
from pathlib import Path

from caliban_toolbox.dataset_builder import DatasetBuilder


def _create_test_npz(path, constant_value=1, X_shape=(10, 20, 20, 3), y_shape=(10, 20, 20, 1)):
    X_data = np.full(X_shape, constant_value)
    y_data = np.full(y_shape, constant_value * 2, dtype='int16')
    np.savez(path, X=X_data, y=y_data)


def _create_minimal_dataset(path):
    """Creates a minimal dataset so that __init__ checks pass"""
    exp_path = os.path.join(path, 'example_exp1')
    os.makedirs(exp_path)
    Path(os.path.join(exp_path, 'metadata.json')).touch()
    Path(os.path.join(exp_path, 'example_data.npz')).touch()


def _create_test_dataset(path, experiments, tissues, platforms, npz_num):
    """Creates an example directory to load data from

    Args:
        path: folder to hold datasets
        experiments: list of experiment names
        tissues: list of tissue types for each experiment
        platforms: list of platform types for each experiment
        npz_num: number of unique NPZ files within each experiment. The NPZs within
            each experiment are constant-valued arrays corresponding to the index of that exp

    Raises:
        ValueError: If tissue_list, platform_list, or NPZ_num have different lengths
    """
    lengths = [len(x) for x in [experiments, tissues, platforms, npz_num]]
    if len(set(lengths)) != 1:
        raise ValueError('All inputs must have the same length')

    for i in range(len(experiments)):
        experiment_folder = os.path.join(path, experiments[i])
        os.makedirs(experiment_folder)

        metadata = dict()
        metadata['tissue'] = tissues[i]
        metadata['platform'] = platforms[i]

        metadata_path = os.path.join(experiment_folder, 'metadata.json')

        with open(metadata_path, 'w') as write_file:
            json.dump(metadata, write_file)

        for npz in range(npz_num[i]):
            _create_test_npz(path=os.path.join(experiment_folder, 'sub_exp_{}.npz'.format(npz)),
                             constant_value=i)


def _create_test_dict(tissues, platforms):
    data = []
    for i in range(len(tissues)):
        current_data = np.full((5, 40, 40, 3), i)
        data.append(current_data)

    data = np.concatenate(data, axis=0)
    X_data = data
    y_data = data[..., :1].astype('int16')

    tissue_list = np.repeat(tissues, 5)
    platform_list = np.repeat(platforms, 5)

    return {'X': X_data, 'y': y_data, 'tissue_list': tissue_list, 'platform_list': platform_list}


def mocked_compute_cell_size(data_dict, by_image):
    """Mocks compute cell size so we don't need to create synthetic data with correct cell size"""
    X = data_dict['X']
    constant_val = X[0, 0, 0, 0]

    # The default resize is 400. We want to create median cell sizes that divide evenly
    # into that number when computing the desired resize ratio

    # even constant_vals will return a median cell size 1/4 the size of the target, odds 4x
    if constant_val % 2 == 0:
        cell_size = 100
    else:
        cell_size = 1600

    return cell_size


def test__init__(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    assert db.dataset_path == tmp_path

    # bad path
    with pytest.raises(ValueError):
        _ = DatasetBuilder(dataset_path='bad_path')


def test__validate_dataset(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(dataset_path=tmp_path)

    # bad path
    with pytest.raises(ValueError):
        db._validate_dataset('bad_path')

    dataset_path = os.path.join(tmp_path, 'example_dataset')
    os.makedirs(dataset_path)

    # no folders in supplied dataset
    with pytest.raises(ValueError):
        db._validate_dataset(dataset_path)

    os.makedirs(os.path.join(dataset_path, 'experiment_1'))
    Path(os.path.join(dataset_path, 'experiment_1', 'example_file.npz')).touch()

    # supplied experiment has an NPZ and no metadata file
    with pytest.raises(ValueError):
        db._validate_dataset(tmp_path)

    # directory has a metadata file and no NPZ
    os.remove(os.path.join(dataset_path, 'experiment_1', 'example_file.npz'))
    Path(os.path.join(dataset_path, 'experiment_1', 'metadata.json')).touch()

    with pytest.raises(ValueError):
        db._validate_dataset(os.path.join(tmp_path))


def test__get_metadata(tmp_path):
    tissues = ['tissue1', 'tissue2']
    platforms = ['platform1', 'platform2']
    experiments = ['exp1', 'exp2']
    npzs = [1, 1]

    _create_test_dataset(path=tmp_path, experiments=experiments, platforms=platforms,
                         tissues=tissues, npz_num=npzs)

    db = DatasetBuilder(tmp_path)
    for i in range(len(experiments)):
        metadata = db._get_metadata(os.path.join(tmp_path, experiments[i]))
        assert metadata['tissue'] == tissues[i]
        assert metadata['platform'] == platforms[i]


def test__identify_tissue_and_platform_types(tmp_path):
    # create dataset
    experiments = ['exp{}'.format(i) for i in range(5)]
    tissues = ['tissue1', 'tissue2', 'tissue3', 'tissue2', 'tissue1']
    platforms = ['platform1', 'platform1', 'platform2', 'platform2', 'platform3']
    npz_num = [1] * 5
    _create_test_dataset(tmp_path, experiments=experiments, tissues=tissues,
                         platforms=platforms, npz_num=npz_num)

    db = DatasetBuilder(dataset_path=tmp_path)

    db._identify_tissue_and_platform_types()

    # check that all tissues and platforms added
    assert set(db.all_tissues) == set(tissues)
    assert set(db.all_platforms) == set(platforms)


def test__load_experiment_single_npz(tmp_path):
    experiments, tissues, platforms, npz_num = ['exp1'], ['tissue1'], ['platform1'], [1]
    _create_test_dataset(tmp_path, experiments=experiments, tissues=tissues,
                         platforms=platforms, npz_num=npz_num)

    # initialize db
    db = DatasetBuilder(tmp_path)

    # load dataset
    X, y, tissue, platform = db._load_experiment(os.path.join(tmp_path, experiments[0]))

    # A single NPZ with 10 images
    assert X.shape[0] == 10
    assert y.shape[0] == 10

    assert tissue == tissues[0]
    assert platform == platforms[0]


def test__load_experiment_multiple_npz(tmp_path):
    experiments, tissues, platforms, npz_num = ['exp1'], ['tissue1'], ['platform1'], [5]
    _create_test_dataset(tmp_path, experiments=experiments, tissues=tissues,
                         platforms=platforms, npz_num=npz_num)

    # initialize db
    db = DatasetBuilder(tmp_path)

    # load dataset
    X, y, tissue, platform = db._load_experiment(os.path.join(tmp_path, experiments[0]))

    # 5 NPZs with 10 images each
    assert X.shape[0] == 50
    assert y.shape[0] == 50

    assert tissue == tissues[0]
    assert platform == platforms[0]


def test__load_all_experiments(tmp_path):
    # create dataset
    experiments = ['exp{}'.format(i) for i in range(5)]
    tissues = ['tissue1', 'tissue2', 'tissue3', 'tissue4', 'tissue5']
    platforms = ['platform5', 'platform4', 'platform3', 'platform2', 'platform1']
    npz_num = [2, 2, 4, 6, 8]
    _create_test_dataset(tmp_path, experiments=experiments, tissues=tissues,
                         platforms=platforms, npz_num=npz_num)

    total_img_num = np.sum(npz_num) * 10

    # initialize db
    db = DatasetBuilder(tmp_path)
    db._identify_tissue_and_platform_types()

    train_ratio, val_ratio, test_ratio = 0.7, 0.2, 0.1

    db._load_all_experiments(data_split=[train_ratio, val_ratio, test_ratio], seed=None)

    # get outputs
    train_dict, val_dict, test_dict = db.train_dict, db.val_dict, db.test_dict

    # check that splits were performed correctly
    for ratio, dict in zip((train_ratio, val_ratio, test_ratio),
                           (train_dict, val_dict, test_dict)):

        X_data, y_data = dict['X'], dict['y']
        assert X_data.shape[0] == ratio * total_img_num
        assert y_data.shape[0] == ratio * total_img_num

        tissue_list, platform_list = dict['tissue_list'], dict['platform_list']
        assert len(tissue_list) == len(platform_list) == X_data.shape[0]

    # check that the metadata maps to the correct images
    for dict in (train_dict, val_dict, test_dict):
        X_data, tissue_list, platform_list = dict['X'], dict['tissue_list'], dict['platform_list']

        # loop over each tissue type, and check that the NPZ is filled with correct constant value
        for constant_val, tissue in enumerate(tissues):

            # index of images with matching tissue type
            tissue_idx = tissue_list == tissue

            images = X_data[tissue_idx]
            assert np.all(images == constant_val)

        # loop over each platform type, and check that the NPZ contains correct constant value
        for constant_val, platform in enumerate(platforms):

            # index of images with matching platform type
            platform_idx = platform_list == platform

            images = X_data[platform_idx]
            assert np.all(images == constant_val)


def test__subset_data_dict(tmp_path):
    _create_minimal_dataset(tmp_path)

    X = np.arange(100)
    y = np.arange(100)
    tissue_list = np.array(['tissue1'] * 10 + ['tissue2'] * 50 + ['tissue3'] * 40)
    platform_list = np.array(['platform1'] * 20 + ['platform2'] * 40 + ['platform3'] * 40)
    data_dict = {'X': X, 'y': y, 'tissue_list': tissue_list, 'platform_list': platform_list}

    db = DatasetBuilder(tmp_path)

    # all tissues, one platform
    tissues = ['tissue1', 'tissue2', 'tissue3']
    platforms = ['platform1']
    subset_dict = db._subset_data_dict(data_dict=data_dict, tissues=tissues, platforms=platforms)
    X_subset = subset_dict['X']
    keep_idx = np.isin(platform_list, platforms)

    assert np.all(X_subset == X[keep_idx])

    # all platforms, one tissue
    tissues = np.array(['tissue2'])
    platforms = np.array(['platform1', 'platform2', 'platform3'])
    subset_dict = db._subset_data_dict(data_dict=data_dict, tissues=tissues, platforms=platforms)
    X_subset = subset_dict['X']
    keep_idx = np.isin(tissue_list, tissues)

    assert np.all(X_subset == X[keep_idx])

    # drop tissue 1 and platform 3
    tissues = np.array(['tissue2', 'tissue3'])
    platforms = np.array(['platform1', 'platform2'])
    subset_dict = db._subset_data_dict(data_dict=data_dict, tissues=tissues, platforms=platforms)
    X_subset = subset_dict['X']
    platform_keep_idx = np.isin(platform_list, platforms)
    tissue_keep_idx = np.isin(tissue_list, tissues)
    keep_idx = np.logical_and(platform_keep_idx, tissue_keep_idx)

    assert np.all(X_subset == X[keep_idx])

    # tissue/platform combination that doesn't exist
    tissues = np.array(['tissue1'])
    platforms = np.array(['platform3'])
    with pytest.raises(ValueError):
        _ = db._subset_data_dict(data_dict=data_dict, tissues=tissues, platforms=platforms)


def test__reshape_dict_no_resize(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    # create dict
    tissues = ['tissue1', 'tissue2', 'tissue3']
    platforms = ['platform1', 'platform2', 'platform3']
    data_dict = _create_test_dict(tissues=tissues, platforms=platforms)

    # this is 1/2 the size on each dimension as original, so we expect 4x more crops
    output_shape = (20, 20)

    reshaped_dict = db._reshape_dict(data_dict=data_dict, resize=False, output_shape=output_shape)
    X_reshaped, tissue_list_reshaped = reshaped_dict['X'], reshaped_dict['tissue_list']
    assert X_reshaped.shape[1:3] == output_shape

    assert X_reshaped.shape[0] == 4 * data_dict['X'].shape[0]

    # make sure that for each tissue, the arrays with correct value have correct tissue label
    for constant_val, tissue in enumerate(tissues):
        tissue_idx = X_reshaped[:, 0, 0, 0] == constant_val
        tissue_labels = np.array(tissue_list_reshaped)[tissue_idx]
        assert np.all(tissue_labels == tissue)


def test__reshape_dict_by_value(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    # create dict
    tissues = ['tissue1', 'tissue2', 'tissue3']
    platforms = ['platform1', 'platform2', 'platform3']
    data_dict = _create_test_dict(tissues=tissues, platforms=platforms)

    # same size as input data
    output_shape = (40, 40)

    reshaped_dict = db._reshape_dict(data_dict=data_dict, resize=3,
                                     output_shape=output_shape)
    X_reshaped, tissue_list_reshaped = reshaped_dict['X'], reshaped_dict['tissue_list']
    assert X_reshaped.shape[1:3] == output_shape

    # make sure that for each tissue, the arrays with correct value have correct tissue label
    for constant_val, tissue in enumerate(tissues):
        # each image was tagged with a different, compute that here
        image_val = np.max(X_reshaped, axis=(1, 2, 3))

        tissue_idx = image_val == constant_val
        tissue_labels = np.array(tissue_list_reshaped)[tissue_idx]
        assert np.all(tissue_labels == tissue)

        # There were originally 5 images of each tissue type. Each dimension was resized 3x,
        # so there should be 9x more images
        assert len(tissue_labels) == 5 * 9

    # now with a resize to make images smaller
    reshaped_dict = db._reshape_dict(data_dict=data_dict, resize=0.5,
                                     output_shape=output_shape)
    X_reshaped, tissue_list_reshaped = reshaped_dict['X'], reshaped_dict['tissue_list']
    assert X_reshaped.shape[1:3] == output_shape

    # make sure that for each tissue, the arrays with correct value have correct tissue label
    for constant_val, tissue in enumerate(tissues):
        # each image was tagged with a different, compute that here
        image_val = np.max(X_reshaped, axis=(1, 2, 3))

        tissue_idx = image_val == constant_val
        tissue_labels = np.array(tissue_list_reshaped)[tissue_idx]
        assert np.all(tissue_labels == tissue)

        # There were originally 5 images of each tissue type. Each dimension was resized 0.5,
        # and because the images are padded there should be the same total number of images
        assert len(tissue_labels) == 5


def test__reshape_dict_by_tissue(tmp_path, mocker):
    mocker.patch('caliban_toolbox.dataset_builder.compute_cell_size', mocked_compute_cell_size)
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    # create dict
    tissues = ['tissue1', 'tissue2', 'tissue3']
    platforms = ['platform1', 'platform2', 'platform3']
    data_dict = _create_test_dict(tissues=tissues, platforms=platforms)

    # same size as input data
    output_shape = (40, 40)

    reshaped_dict = db._reshape_dict(data_dict=data_dict, resize='by_tissue',
                                     output_shape=output_shape)
    X_reshaped, tissue_list_reshaped = reshaped_dict['X'], reshaped_dict['tissue_list']
    assert X_reshaped.shape[1:3] == output_shape

    # make sure that for each tissue, the arrays with correct value have correct tissue label
    for constant_val, tissue in enumerate(tissues):
        # each image was tagged with a different, compute that here
        image_val = np.max(X_reshaped, axis=(1, 2, 3))

        tissue_idx = image_val == constant_val
        tissue_labels = np.array(tissue_list_reshaped)[tissue_idx]
        assert np.all(tissue_labels == tissue)

        # There were originally 5 images of each tissue type. Tissue types with even values
        # are resized to be 2x larger on each dimension, and should have 4x more images
        if constant_val % 2 == 0:
            assert len(tissue_labels) == 5 * 4
        # tissue types with odd values are resized to be smaller, which leads to same number
        # of unique images due to padding
        else:
            assert len(tissue_labels) == 5


# TODO: Is there a way to check the resize value of each unique image?
def test__reshape_dict_by_image(tmp_path, mocker):
    mocker.patch('caliban_toolbox.dataset_builder.compute_cell_size', mocked_compute_cell_size)
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    # create dict
    tissues = ['tissue1', 'tissue2', 'tissue3']
    platforms = ['platform1', 'platform2', 'platform3']
    data_dict = _create_test_dict(tissues=tissues, platforms=platforms)

    # same size as input data
    output_shape = (40, 40)

    reshaped_dict = db._reshape_dict(data_dict=data_dict, resize='by_image',
                                     output_shape=output_shape)
    X_reshaped, tissue_list_reshaped = reshaped_dict['X'], reshaped_dict['tissue_list']
    assert X_reshaped.shape[1:3] == output_shape

    # make sure that for each tissue, the arrays with correct value have correct tissue label
    for constant_val, tissue in enumerate(tissues):
        # each image was tagged with a different, compute that here
        image_val = np.max(X_reshaped, axis=(1, 2, 3))

        tissue_idx = image_val == constant_val
        tissue_labels = np.array(tissue_list_reshaped)[tissue_idx]
        assert np.all(tissue_labels == tissue)

        # There were originally 5 images of each tissue type. Tissue types with even values
        # are resized to be 2x larger on each dimension, and should have 4x more images
        if constant_val % 2 == 0:
            assert len(tissue_labels) == 5 * 4
        # tissue types with odd values are resized to be smaller, which leads to same number
        # of unique images due to padding
        else:
            assert len(tissue_labels) == 5


def test__clean_labels(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    test_label = np.zeros((50, 50), dtype='int')
    test_label[:10, :10] = 2
    test_label[12:17, 12:17] = 2
    test_label[20:22, 22:23] = 3

    test_labels = np.zeros((2, 50, 50, 1), dtype='int')
    test_labels[0, ..., 0] = test_label

    test_X = np.zeros_like(test_labels)
    test_tissue = np.array(['tissue1', 'tissue2'])
    test_platform = np.array(['platform2', 'platform3'])

    test_dict = {'X': test_X, 'y': test_labels, 'tissue_list': test_tissue,
                 'platform_list': test_platform}

    # relabel sequential
    cleaned_dict = db._clean_labels(data_dict=test_dict, relabel=False)
    assert len(np.unique(cleaned_dict['y'])) == 2 + 1  # 0 for background

    # true relabel
    cleaned_dict = db._clean_labels(data_dict=test_dict, relabel=True)
    assert len(np.unique(cleaned_dict['y'])) == 3 + 1

    # remove small objects
    cleaned_dict = db._clean_labels(data_dict=test_dict, relabel=True,
                                    small_object_threshold=15)
    assert len(np.unique(cleaned_dict['y'])) == 2 + 1

    # remove sparse images
    cleaned_dict = db._clean_labels(data_dict=test_dict, relabel=True, min_objects=1)
    assert cleaned_dict['y'].shape[0] == 1
    assert cleaned_dict['X'].shape[0] == 1
    assert len(cleaned_dict['tissue_list']) == 1
    assert cleaned_dict['tissue_list'][0] == 'tissue1'
    assert len(cleaned_dict['platform_list']) == 1
    assert cleaned_dict['platform_list'][0] == 'platform2'


def test__balance_dict(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    X_data = np.random.rand(9, 10, 10, 3)
    y_data = np.random.rand(9, 10, 10, 1)
    tissue_list = np.array(['tissue1'] * 3 + ['tissue2'] * 3 + ['tissue3'] * 3)
    platform_list = np.array(['platform1'] * 3 + ['platform2'] * 3 + ['platform3'] * 3)

    balanced_dict = {'X': X_data, 'y': y_data, 'tissue_list': tissue_list,
                     'platform_list': platform_list}
    output_dict = db._balance_dict(data_dict=balanced_dict, seed=0, category='tissue_list')

    # data is already balanced, all items should be identical
    for key in output_dict:
        assert np.all(output_dict[key] == balanced_dict[key])

    # tissue 3 has most, others need to be upsampled
    tissue_list = np.array(['tissue1'] * 1 + ['tissue2'] * 2 + ['tissue3'] * 6)
    unbalanced_dict = {'X': X_data, 'y': y_data, 'tissue_list': tissue_list,
                       'platform_list': platform_list}
    output_dict = db._balance_dict(data_dict=unbalanced_dict, seed=0, category='tissue_list')

    # tissue 3 is unchanged
    for key in output_dict:
        assert np.all(output_dict[key][-6:] == unbalanced_dict[key][-6:])

    # tissue 1 only has a single example, all copies should be equal
    tissue1_idx = np.where(output_dict['tissue_list'] == 'tissue1')[0]
    for key in output_dict:
        vals = output_dict[key]
        for idx in tissue1_idx:
            new_val = vals[idx]
            old_val = unbalanced_dict[key][0]
            assert np.all(new_val == old_val)

    # tissue 2 has 2 examples, all copies should be equal to one of those values
    tissue2_idx = np.where(output_dict['tissue_list'] == 'tissue2')[0]
    for key in output_dict:
        vals = output_dict[key]
        for idx in tissue2_idx:
            new_val = vals[idx]
            old_val1 = unbalanced_dict[key][1]
            old_val2 = unbalanced_dict[key][2]
            assert np.all(new_val == old_val1) or np.all(new_val == old_val2)

    # check with same seed
    output_dict_same_seed = db._balance_dict(data_dict=unbalanced_dict, seed=0,
                                             category='tissue_list')

    for key in output_dict_same_seed:
        assert np.all(output_dict_same_seed[key] == output_dict[key])

    # check with different seed
    output_dict_diff_seed = db._balance_dict(data_dict=unbalanced_dict, seed=1,
                                             category='tissue_list')

    for key in ['X', 'y']:
        assert not np.all(output_dict_diff_seed[key] == output_dict[key])


def test__validate_categories(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    category_list = ['cat1', 'cat2', 'cat3']

    # convert single category to list
    supplied_categories = 'cat1'
    validated = db._validate_categories(category_list=category_list,
                                        supplied_categories=supplied_categories)
    assert validated == [supplied_categories]

    # convert 'all' to list of all categories
    supplied_categories = 'all'
    validated = db._validate_categories(category_list=category_list,
                                        supplied_categories=supplied_categories)
    assert np.all(validated == category_list)

    # convert 'all' to list of all categories
    supplied_categories = ['cat1', 'cat3']
    validated = db._validate_categories(category_list=category_list,
                                        supplied_categories=supplied_categories)
    assert np.all(validated == supplied_categories)

    # invalid string
    supplied_categories = 'cat4'
    with pytest.raises(ValueError):
        _ = db._validate_categories(category_list=category_list,
                                    supplied_categories=supplied_categories)

    # invalid list
    supplied_categories = ['cat4', 'cat1']
    with pytest.raises(ValueError):
        _ = db._validate_categories(category_list=category_list,
                                    supplied_categories=supplied_categories)


def test__validate_output_shape(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    # make sure list or tuple is converted
    output_shapes = [[222, 333], (222, 333)]
    for output_shape in output_shapes:
        validated_shape = db._validate_output_shape(output_shape)
        assert validated_shape == [output_shape, output_shape, output_shape]

    # not all splits specified
    output_shape = [(123, 456), (789, 1011)]
    with pytest.raises(ValueError):
        _ = db._validate_output_shape(output_shape=output_shape)

    # not all splits have 2 entries
    output_shape = [(12, 34), (56, 78), (910, 1112, 1314)]
    with pytest.raises(ValueError):
        _ = db._validate_output_shape(output_shape=output_shape)

    # too many splits
    output_shape = [(12, 34), (56, 78), (910, 1112), (1314, )]
    with pytest.raises(ValueError):
        _ = db._validate_output_shape(output_shape=output_shape)

    # not a list/tuple
    output_shape = 56
    with pytest.raises(ValueError):
        _ = db._validate_output_shape(output_shape=output_shape)


def test_build_dataset(tmp_path):
    # create dataset
    experiments = ['exp{}'.format(i) for i in range(5)]
    tissues = ['tissue1', 'tissue2', 'tissue3', 'tissue4', 'tissue5']
    platforms = ['platform5', 'platform4', 'platform3', 'platform2', 'platform1']
    npz_num = [2, 2, 4, 6, 8]
    _create_test_dataset(tmp_path, experiments=experiments, tissues=tissues,
                         platforms=platforms, npz_num=npz_num)

    db = DatasetBuilder(tmp_path)

    # dataset with all data included
    output_dicts = db.build_dataset(tissues=tissues, platforms=platforms, output_shape=(20, 20))

    for dict in output_dicts:
        # make sure correct tissues and platforms loaded
        current_tissues = dict['tissue_list']
        current_platforms = dict['platform_list']
        assert set(current_tissues) == set(tissues)
        assert set(current_platforms) == set(platforms)

    # dataset with only a subset included
    tissues, platforms = tissues[:3], platforms[:3]
    output_dicts = db.build_dataset(tissues=tissues, platforms=platforms, output_shape=(20, 20))

    for dict in output_dicts:
        # make sure correct tissues and platforms loaded
        current_tissues = dict['tissue_list']
        current_platforms = dict['platform_list']
        assert set(current_tissues) == set(tissues)
        assert set(current_platforms) == set(platforms)

    # cropping to 1/2 the size, there should be 4x more crops
    output_dicts_crop = db.build_dataset(tissues=tissues, platforms=platforms,
                                         output_shape=(10, 10), relabel=True)

    for base_dict, crop_dict in zip(output_dicts, output_dicts_crop):
        X_base, X_crop = base_dict['X'], crop_dict['X']
        assert X_base.shape[0] * 4 == X_crop.shape[0]

    # check that NPZs have been relabeled
    for current_dict in output_dicts_crop:
        assert len(np.unique(current_dict['y'])) == 2

    # different sizes for different splits
    output_dicts_diff_sizes = db.build_dataset(tissues=tissues, platforms=platforms,
                                               output_shape=[(10, 10), (15, 15), (20, 20)])

    assert output_dicts_diff_sizes[0]['X'].shape[1:3] == (10, 10)
    assert output_dicts_diff_sizes[1]['X'].shape[1:3] == (15, 15)
    assert output_dicts_diff_sizes[2]['X'].shape[1:3] == (20, 20)

    # full runthrough with default options changed
    _ = db.build_dataset(tissues='all', platforms=platforms, output_shape=(10, 10),
                         relabel=True, resize='by_image', small_object_threshold=5,
                         balance=True)


def test_summarize_dataset(tmp_path):
    _create_minimal_dataset(tmp_path)
    db = DatasetBuilder(tmp_path)

    # create dict
    tissues = ['tissue1', 'tissue2', 'tissue3']
    platforms = ['platform1', 'platform2', 'platform3']
    train_dict = _create_test_dict(tissues=tissues, platforms=platforms)
    val_dict = _create_test_dict(tissues=tissues[1:], platforms=platforms[1:])
    test_dict = _create_test_dict(tissues=tissues[:-1], platforms=platforms[:-1])

    # make sure each dict has 2 cells in every image for counting purposes
    for current_dict in [train_dict, val_dict, test_dict]:
        current_labels = current_dict['y']
        current_labels[:, 0, 0, 0] = 5
        current_labels[:, 10, 0, 0] = 12

        current_dict['y'] = current_labels

    db.train_dict = train_dict
    db.val_dict = val_dict
    db.test_dict = test_dict

    tissue_dict, platform_dict = db.summarize_dataset()

    # check that all tissues and platforms are present
    for i in range(len(tissues)):
        assert tissues[i] in tissue_dict
        assert platforms[i] in platform_dict

    # Check that math is computed correctly
    for dict in [tissue_dict, platform_dict]:
        for key in list(dict.keys()):

            # each image has only two cells
            cell_num = dict[key]['cell_num']
            image_num = dict[key]['image_num']
            assert cell_num == image_num * 2

            # middle categories are present in all three dicts, and hence have 15
            if key in ['tissue2', 'platform2']:
                assert image_num == 15
            else:
                assert image_num == 10
