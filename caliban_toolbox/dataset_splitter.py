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
import numpy as np


class DatasetSplitter(object):
    def __init__(self, seed=0, splits=None):
        """Class to split a dataset into sequentially increasing tranches for model training

        Args:
            seed: random seed for splitting
            splits: list of proportions for each split

        Raises:
            ValueError: If splits are not sequentially increasing between (0, 1]
        """

        self.seed = seed

        if splits is None:
            self.splits = [0.05, 0.10, 0.25, 0.5, 0.75, 1]
        else:
            splits.sort()
            if splits[0] <= 0:
                raise ValueError('Smallest split must be non-zero, got {}'.format(splits[0]))
            if splits[-1] > 1:
                raise ValueError('Largest split cannot be greater than 1, '
                                 'got {}'.format(splits[-1]))
            ids, counts = np.unique(splits, return_counts=True)
            if np.any(counts != 1):
                raise ValueError('Duplicate splits are not allowed, each split must be uniqe')
            self.splits = splits

    def _validate_dict(self, train_dict):
        if 'X' not in train_dict or 'y' not in train_dict:
            raise ValueError('X and y must be keys in the training dictionary')

    def _duplicate_indices(self, indices, min_size):
        """Duplicates supplied indices to that there are min_size number

        Args:
            indices: array specifying indices of images to be included
            min_size: minimum number of images in split

        Returns:
            array: duplicate indices
        """

        multiplier = np.ceil(min_size / len(indices))
        new_indices = np.repeat(indices, multiplier)
        new_indices = new_indices[:min_size]

        return new_indices

    def split(self, train_dict, min_size=1):
        """Split training dict

        Args:
            train_dict: dictionary containing paired X and y data
            min_size: minimum number of images for each split. If supplied split size leads to a
                split with fewer than min_size, duplicates included images up to specified count

        Returns:
            dict: dict of dicts containing each split
        """
        self._validate_dict(train_dict)
        X = train_dict['X']
        y = train_dict['y']
        N_batches = X.shape[0]
        index = np.arange(N_batches)

        # randomize index so that we can take sequentially larger splits
        permuted_index = np.random.RandomState(seed=self.seed).permutation(index)

        split_dict = {}
        for split in self.splits:
            # minimum of 1 image per split
            train_size = max(int(split * N_batches), 1)
            split_idx = permuted_index[0:train_size]

            # duplicate indices up to minimum batch size if necessary
            if len(split_idx) < min_size:
                split_idx = self._duplicate_indices(indices=split_idx, min_size=min_size)

            new_train_dict = {}
            new_train_dict['X'] = X[split_idx]
            new_train_dict['y'] = y[split_idx]
            split_dict[str(split)] = new_train_dict

        return split_dict
