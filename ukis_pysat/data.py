#!/usr/bin/env python3

import logging
import math
from itertools import product

import dask.array as da
import numpy as np
import rasterio
import rasterio.mask
from rasterio import windows
from rasterio.io import MemoryFile
from rasterio.warp import calculate_default_transform, reproject
from rio_toa import reflectance, brightness_temp, toa_utils
from shapely.geometry import box, polygon

from ukis_pysat.members import Platform

logger = logging.getLogger(__name__)


class Image:
    def __init__(self, path=None, dataset=None, arr=None):
        if path:
            if isinstance(path, str):
                self.dataset = rasterio.open(path)
                self.arr = self.dataset.read()
            else:
                raise TypeError(f"path must be of type str")
        else:
            if isinstance(dataset, rasterio.io.DatasetReader) and isinstance(arr, np.ndarray):
                self.dataset = dataset
                self.arr = arr
            else:
                raise TypeError(
                    f"dataset must be of type rasterio.io.DatasetReader and arr must be of type " f"numpy.ndarray"
                )
        self.transform = self.dataset.transform
        self.crs = self.dataset.crs
        self.da_arr = None

    def get_valid_data_bbox(self, nodata=0):
        """bounding box covering the input array's valid data pixels.

        :param nodata: nodata value, optional (default: 0)
        :return: tuple with valid data bounds
        """
        valid_data_window = windows.get_data_window(self.arr, nodata=nodata)
        return windows.bounds(valid_data_window, windows.transform(valid_data_window, self.transform))

    def mask_image(self, bbox, crop=True, pad=False, **kwargs):
        """
        TODO https://github.com/mapbox/rasterio/issues/995
        :param bbox: bounding box of type tuple or Shapely Polygon
        :param crop: bool, see rasterio.mask. Optional, (default: True)
        :param pad: pads image, should only be used when bbox.bounds extent img.bounds, optional (default: False)
        """
        if pad:
            self.dataset = self._pad_to_bbox(bbox, **kwargs).open()

        if isinstance(bbox, polygon.Polygon):
            self.arr, self.transform = rasterio.mask.mask(self.dataset, [bbox], crop=crop)
        elif isinstance(bbox, tuple):
            self.arr, self.transform = rasterio.mask.mask(self.dataset, [box(*bbox)], crop=crop)
        else:
            raise TypeError(f"bbox must be of type tuple or Shapely Polygon")

    def _pad_to_bbox(self, bbox, mode="constant", constant_values=0):
        """Buffers array with biggest difference to bbox and adjusts affine transform matrix. Can be used to fill
        array with nodata values before masking in case bbox only partially overlaps dataset bounds.

        :param bbox: bounding box of type tuple or Shapely Polygon
        :param mode: str, how to pad, see rasterio.pad. Optional (default: 'constant')
        :param constant_values: nodata value, padding should be filled with, optional (default: 0)
        :return: open, buffered dataset in memory
        """
        if isinstance(bbox, polygon.Polygon):
            bbox = bbox.bounds
        elif isinstance(bbox, tuple):
            pass
        else:
            raise TypeError(f"bbox must be of type tuple or Shapely Polygon")

        max_diff_ur = np.max(np.subtract(bbox[2:], tuple(self.dataset.bounds[2:])))
        max_diff_ll = np.max(np.subtract(tuple(self.dataset.bounds[:2]), bbox[:2]))
        max_diff = max(max_diff_ll, max_diff_ur)  # buffer in units

        pad_width = math.ceil(max_diff / self.transform.to_gdal()[1])  # units / pixel_size

        destination = np.zeros(
            (self.dataset.count, self.arr.shape[1] + 2 * pad_width, self.arr.shape[2] + 2 * pad_width,), self.arr.dtype,
        )

        for i in range(0, self.dataset.count):
            destination[i], self.transform = rasterio.pad(
                self.arr[0], self.transform, pad_width, mode, constant_values=constant_values,
            )

        self.arr = destination

        mem_profile = self.dataset.meta
        mem_profile.update(
            {"height": self.arr.shape[-2], "width": self.arr.shape[-1], "transform": self.transform,}
        )

        memfile = MemoryFile()
        ds = memfile.open(**mem_profile)
        ds.write(self.arr)

        return memfile

    def warp(self, dst_crs, resampling_method=0, num_threads=4, resolution=None):
        """Reproject a source raster to a destination raster.

        :param dst_crs: CRS or dict, Target coordinate reference system.
        :param resampling_method: Resampling algorithm, int, defaults to 0 (Nearest)
            numbers: https://github.com/mapbox/rasterio/blob/master/rasterio/enums.py#L28
        :param num_threads: int, number of workers, optional (default: 4)
        :param resolution: tuple (x resolution, y resolution) or float, optional.
            Target resolution, in units of target coordinate reference system.
        """
        # output dimensions and transform for reprojection.
        if resolution:
            transform, width, height = calculate_default_transform(
                self.dataset.crs,
                dst_crs,
                self.dataset.width,
                self.dataset.height,
                *self.dataset.bounds,
                resolution=resolution,
            )
        else:
            transform, width, height = calculate_default_transform(
                self.dataset.crs, dst_crs, self.dataset.width, self.dataset.height, *self.dataset.bounds,
            )

        destination = np.zeros((self.dataset.count, height, width), self.arr.dtype)

        for i in range(0, self.dataset.count):
            reproject(
                source=rasterio.band(self.dataset, i + 1),  # index starting at 1
                destination=destination[i],
                src_transform=self.dataset.transform,
                src_crs=self.dataset.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=resampling_method,
                num_threads=num_threads,
            )

        # update for further processing
        self.arr = destination
        self.transform = transform
        self.crs = dst_crs

    def dn2toa(self, platform, metadata=None, wavelengths=None):
        """This method converts digital numbers to top of atmosphere reflectance, like described here:
        https://www.usgs.gov/land-resources/nli/landsat/using-usgs-landsat-level-1-data-product
        TODO rio-toa does not seem to be maintained anymore

        :param platform: image platform, possible Platform.Landsat[5, 7, 8] or Platform.Sentinel2 (<enum 'Platform'>).
        :param metadata: path to metadata file for Landsat (str).
        :param wavelengths: like ["Blue", "Green", "Red", "NIR", "SWIR1", "TIRS", "SWIR2"] for Landsat-5 (list of str).
        """
        if platform in [
            Platform.Landsat5,
            Platform.Landsat7,
            Platform.Landsat8,
        ]:
            if metadata is None:
                logger.warning(
                    "No metadata file provided. Using a simplified DN2TOA conversion that ignores sun angle and "
                    "band specific rescaling factors."
                )
                simple_toa = 0.00002 * self.arr.astype(np.float32) + (-0.100000)
                self.arr = np.array(np.dstack(simple_toa))
            else:
                # if metadata file is provided use a more sophisticated conversion that accounts for the sun angle
                # get factors from metadata file
                mtl = toa_utils._load_mtl(metadata)  # no obvious reason not to call this
                metadata = mtl["L1_METADATA_FILE"]
                sun_elevation = metadata["IMAGE_ATTRIBUTES"]["SUN_ELEVATION"]
                toa = []

                for idx, b in enumerate(sorted(self._lookup_bands(platform, wavelengths))):
                    multiplicative_rescaling_factors = metadata["RADIOMETRIC_RESCALING"][f"REFLECTANCE_MULT_BAND_{b}"]
                    additive_rescaling_factors = metadata["RADIOMETRIC_RESCALING"][f"REFLECTANCE_ADD_BAND_{b}"]

                    if platform == Platform.Landsat8:  # exception for Landsat-8
                        if b in ["10", "11"]:
                            thermal_conversion_constant1 = metadata["THERMAL_CONSTANTS"][f"K1_CONSTANT_BAND_{b}"]
                            thermal_conversion_constant2 = metadata["THERMAL_CONSTANTS"][f"K2_CONSTANT_BAND_{b}"]
                            toa.append(
                                brightness_temp.brightness_temp(
                                    self.arr[:, :, idx],
                                    ML=multiplicative_rescaling_factors,
                                    AL=additive_rescaling_factors,
                                    K1=thermal_conversion_constant1,
                                    K2=thermal_conversion_constant2,
                                )
                            )
                            continue
                    else:
                        if b.startswith("6"):
                            thermal_conversion_constant1 = metadata["TIRS_THERMAL_CONSTANTS"][f"K1_CONSTANT_BAND_{b}"]
                            thermal_conversion_constant2 = metadata["TIRS_THERMAL_CONSTANTS"][f"K2_CONSTANT_BAND_{b}"]
                            toa.append(
                                brightness_temp.brightness_temp(
                                    self.arr[:, :, idx],
                                    ML=multiplicative_rescaling_factors,
                                    AL=additive_rescaling_factors,
                                    K1=thermal_conversion_constant1,
                                    K2=thermal_conversion_constant2,
                                )
                            )
                            continue

                    toa.append(
                        reflectance.reflectance(
                            self.arr[:, :, idx],
                            MR=multiplicative_rescaling_factors,
                            AR=additive_rescaling_factors,
                            E=sun_elevation,
                        )
                    )

                self.arr = np.array(np.dstack(toa))
        elif platform == Platform.Sentinel2:
            self.arr = self.arr.astype(np.float32) / 10000.0
        else:
            logger.warning(
                f"Cannot convert dn2toa. Platform {platform} not supported [Landsat-5, Landsat-7, Landsat-8, "
                f"Sentinel-2]. "
            )

    @staticmethod
    def _lookup_bands(platform, wavelengths):
        """lookup for bands and their according wavelength for Landsat-5, -7 & -8.

        :param: platform: Platform.Landsat[5, 7, 8]
        :param wavelengths: list like ["Blue", "Green", "Red"]
        :return: list of bands like ["1", "2", "3"]
        """
        wave_bands = {
            Platform.Landsat5: {
                "blue": "1",
                "green": "2",
                "red": "3",
                "nir": "4",
                "swir1": "5",
                "tirs": "6",
                "swir2": "7",
            },
            Platform.Landsat7: {
                "blue": "1",
                "green": "2",
                "red": "3",
                "nir": "4",
                "swir1": "5",
                "tirs1": "6_VCID_1",
                "tirs2": "6_VCID_2",
                "swir2": "7",
            },
            Platform.Landsat8: {
                "aerosol": "1",
                "blue": "2",
                "green": "3",
                "red": "4",
                "nir": "5",
                "swir1": "6",
                "swir2": "7",
                "pan": "9",
                "tirs1": "10",
                "tirs2": "11",
            },
        }

        return [wave_bands[platform][wavelength.lower()] for wavelength in wavelengths]

    def get_tiles(self, width=256, height=256, overlap=0):
        """Calculates rasterio.windows.Window, idea from https://stackoverflow.com/a/54525931

        TODO boundless with 'reflect' padding

        :param width: int, optional (default: 256). Tile size in pixels.
        :param height: int, optional (default: 256). Tile size in pixels.
        :param overlap: int, optional (default: 0). Overlap in pixels.
        :yields: window of tile
        """
        logger.info(f"Get tiles with size {width}x{height}.")
        rows = self.arr.shape[-2]
        cols = self.arr.shape[-1]
        offsets = product(range(0, cols, width), range(0, rows, height))
        bounding_window = windows.Window(col_off=0, row_off=0, width=cols, height=rows)
        for col_off, row_off in offsets:
            yield windows.Window(
                col_off=col_off - overlap,
                row_off=row_off - overlap,
                width=width + 2 * overlap,
                height=height + 2 * overlap,
            ).intersection(
                bounding_window
            )  # clip off window parts not in original array

    def smooth_tiles(self, window_tile):
        # TODO using tukey --> https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.windows.tukey.html
        pass

    def get_subset(self, tile):
        """
        Build a subset of an array. Shape of array is announced with (bands, height, width).
        :param tile:
        :return: Sliced numpy array, bounding box of array slice
        """
        # access window bounds
        bounds = windows.bounds(tile, self.dataset.transform)
        return self.arr[(slice(None),) + tile.toslices()], bounds

    def get_dask_array(self, chunk_size=(1, 6000, 6000)):
        """ transforms numpy to dask array

        :param chunk_size: tuple, size of chunk, optional (default: (1, 6000, 6000))
        :return: dask array
        """
        self.da_arr = da.from_array(self.arr, chunks=chunk_size)
        return self.da_arr

    def write_to_file(self, path_to_file, dtype=rasterio.uint16, driver="GTiff"):
        """
        Write a dataset to file.
        :param path_to_file: str, path to new file
        :param dtype: datatype, optional (default: rasterio.uint16)
        :param driver: str, optional (default: 'GTiff')
        """
        profile = self.dataset.meta
        profile.update(
            {
                "driver": driver,
                "height": self.arr.shape[-2],
                "width": self.arr.shape[-1],
                "dtype": dtype,
                "transform": self.transform,
                "crs": self.crs,
            }
        )

        with rasterio.open(path_to_file, "w", **profile) as dst:
            dst.write(self.arr.astype(dtype))

    def close(self):
        """closes Image"""
        self.dataset.close()


if __name__ == "__main__":
    pass
