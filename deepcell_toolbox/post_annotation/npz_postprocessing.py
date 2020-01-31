# Copyright 2016-2019 David Van Valen at California Institute of Technology
# (Caltech), with support from the Paul Allen Family Foundation, Google,
# & National Institutes of Health (NIH) under Grant U24CA224309-01.
# All rights reserved.
#
# Licensed under a modified Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.github.com/vanvalenlab/deepcell-toolbox/LICENSE
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
import os
import json

import xarray as xr

from skimage.segmentation import relabel_sequential


def load_crops(crop_dir, fov_names, row_crop_size, col_crop_size, num_row_crops, num_col_crops, num_channels,
               save_format):
    """Reads all of the cropped images from a directory, and aggregates them into a single stack

    Inputs:
        crop_dir: path to directory with cropped npz or xarray files
        fov_names: list of unique fov names in dataset
        row_crop_size: size of the crops in rows dimension
        col_crop_size: size of the crops in cols dimension
        num_row_crops: number of crops in rows dimension
        num_col_cops: number of crops in cols dimension
        num_channels: number of channels in imaging data
        save_format: format in which the crops were saved

    Outputs:
        stack: combined array of all labeled images"""

    stack = np.zeros((len(fov_names), num_col_crops*num_row_crops, row_crop_size, col_crop_size, num_channels))

    # loop through all npz files
    for fov_idx, fov_name in enumerate(fov_names):
        crop_idx = 0
        for row in range(num_row_crops):
            for col in range(num_col_crops):

                # if data was saved as npz, load X and y separately then combine
                if save_format == "npz":
                    npz_path = os.path.join(crop_dir, "{}_row_{}_col_{}.npz".format(fov_name, row, col))
                    if os.path.exists(npz_path):
                        temp_npz = np.load(npz_path)
                        stack[fov_idx, crop_idx, ..., :-1] = temp_npz["X"]
                        stack[fov_idx, crop_idx, ..., -1:] = temp_npz["y"]
                    else:
                        # npz not generated, did not contain any labels, keep blank
                        print("could not find npz {}, skipping".format(npz_path))

                # if data was saved as xr, load both X and y simultaneously
                elif save_format == "xr":
                    xr_path = os.path.join(crop_dir, "{}_row_{}_col_{}.xr".format(fov_name, row, col))
                    if os.path.exists(xr_path):
                        temp_xr = xr.open_dataarray(xr_path)
                        stack[fov_idx, crop_idx, ...] = temp_xr
                    else:
                        # npz not generated, did not contain any labels, keep blank
                        print("could not find xr {}, skippiing".format(xr_path))
                crop_idx += 1

    return stack


def stitch_crops(stack, padded_img_shape, row_starts, row_ends, col_starts, col_ends):
    """Takes a stack of annotated labels and stitches them together into a single image

    Inputs:
        stack: stack of crops to be stitched together
        padded_img_shape: shape of the original padded image
        row_starts: list of row indices for crop starts
        row_ends: list of row indices for crops ends
        col_starts: list of col indices for col starts
        col_ends: list of col indices for col ends

    Outputs:
        stitched_image: stitched labels image, sequentially relabeled"""

    # Initialize image
    stitched_image = np.zeros(padded_img_shape)

    # loop through all crops in the stack for each image
    for img in range(stack.shape[0]):
        crop_counter = 0
        for row in range(len(row_starts)):
            for col in range(len(col_starts)):

                # get current crop
                crop = stack[img, crop_counter, ...]

                # increment values to ensure unique labels across final image
                lowest_allowed_val = np.amax(stitched_image[img, ...])
                crop = np.where(crop == 0, crop, crop + lowest_allowed_val)

                # get ids of cells in current crop
                potential_overlap_cells = np.unique(crop)
                potential_overlap_cells = potential_overlap_cells[np.nonzero(potential_overlap_cells)]

                # get values of stitched image at location where crop will be placed
                stitched_crop = stitched_image[img, row_starts[row]:row_ends[row], col_starts[col]:col_ends[col], :]

                # loop through each cell in the crop to determine if it overlaps with another cell in full image
                for cell in potential_overlap_cells:

                    # get cell ids present in stitched image at location of current cell in crop
                    stitched_overlap_vals, stitched_overlap_counts = np.unique(stitched_crop[crop == cell],
                                                                               return_counts=True)
                    stitched_overlap_vals = stitched_overlap_vals[np.nonzero(stitched_overlap_vals)]

                    # if there are overlaps, determine which is greatest, and replace with that value
                    if len(stitched_overlap_vals) > 0:
                        max_overlap = stitched_overlap_vals[np.argmax(stitched_overlap_vals)]
                        crop[crop == cell] = max_overlap

                # combine the crop with the current values in the stitched image
                combined_crop = np.where(stitched_crop > 0, stitched_crop, crop)

                # use this combined crop to update the values of stitched image
                stitched_image[img, row_starts[row]:row_ends[row], col_starts[col]:col_ends[col]] = combined_crop

                crop_counter += 1

    # relabel images to remove skipped cell_ids
    for img in range(stitched_image.shape[0]):
        stitched_image[img, ..., -1], _, _ = relabel_sequential(stitched_image[img, ..., -1])

    return stitched_image


def reconstruct_image_stack(crop_dir, save_format="xr"):
    """High level function to combine crops together into a single stitched image

    Inputs:
        crop_dir: directory where cropped files are stored
        save_format: format that crops were saved in

    Outputs:
        None (saves stitched xarray to folder)"""

    # sanitize inputs
    if not os.path.isdir(crop_dir):
        raise ValueError("crop_dir not a valid directory: {}".format(crop_dir))

    if save_format not in ["xr", "npz"]:
        raise ValueError("save_format needs to be one of ['xr', 'npz'], got {}".format(save_format))

    # unpack JSON data
    with open(os.path.join(crop_dir, "log_data.json")) as json_file:
        log_data = json.load(json_file)

    row_start, row_end = log_data["row_start"], log_data["row_end"]
    col_start, col_end, padded_shape = log_data["col_start"], log_data["col_end"], log_data["padded_shape"]
    row_padding, col_padding, fov_names = log_data["row_padding"], log_data["col_padding"], log_data["fov_names"]
    chan_names = log_data["chan_names"]

    # combine all npz crops into a single stack
    crop_stack = load_crops(crop_dir=crop_dir, fov_names=fov_names, row_crop_size=row_end[0]-row_start[0],
                               col_crop_size=col_end[0]-col_start[0], num_row_crops=len(row_start),
                               num_col_crops=len(col_start), num_channels=len(chan_names), save_format=save_format)

    # stitch crops together into single contiguous image
    stitched_images = stitch_crops(stack=crop_stack, padded_img_shape=padded_shape, row_starts=row_start,
                                   row_ends=row_end, col_starts=col_start, col_ends=col_end)

    # crop image down to original size
    stitched_images = stitched_images[:, 0:(-row_padding), 0:(-col_padding), :]

    stitched_xr = xr.DataArray(data=stitched_images,
                               coords=[fov_names, range(stitched_images.shape[1]), range(stitched_images.shape[2]),
                                       chan_names], dims=["fovs", "rows", "cols", "channels"])

    stitched_xr.to_netcdf(os.path.join(crop_dir, "stitched_images.nc"))

