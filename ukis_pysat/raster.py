# -*- coding: utf-8 -*-

import math
from itertools import product
from pathlib import Path

from ukis_pysat.members import Platform

try:
    import numpy as np
    import rasterio
    import rasterio.dtypes
    import rasterio.mask
    import rasterio.plot
    import rasterio.warp
    import rasterio.windows
    import shapely.geometry
    from rasterio.io import MemoryFile
    from rio_toa import reflectance, brightness_temp, toa_utils
except ImportError as e:
    msg = (
        "ukis_pysat.raster dependencies are not installed.\n\n"
        "Please pip install as follows:\n\n"
        "  python -m pip install ukis-pysat[raster] --upgrade"
    )
    raise ImportError(str(e) + "\n\n" + msg)


class Image:

    da_arr = None

    def __init__(self, data, dimorder="first", crs=None, transform=None, nodata=None):
        """
        :param data: rasterio.io.DatasetReader or path to raster or np.ndarray of shape (bands, rows, columns)
        :param dimorder: Order of channels or bands 'first' or 'last' (default: 'first')
        :param crs: Coordinate reference system used when creating form array. If 'data' is np.ndarray this is required (default: None)
        :param transform: Affine transformation mapping the pixel space to geographic space. If 'data' is np.ndarray this is required (default: None)
        :param nodata: nodata value only used when creating from np.ndarray, otherwise this has no effects, optional (default: None)

        """
        if dimorder in ("first", "last"):
            self.dimorder = dimorder
        else:
            raise TypeError("dimorder for bands or channels must be either 'first' or 'last'.")

        if isinstance(data, rasterio.io.DatasetReader):
            self.dataset = data
            self.__arr = self.dataset.read()

        elif isinstance(data, (str, Path)):
            self.dataset = rasterio.open(data)
            self.__arr = self.dataset.read()

        elif isinstance(data, np.ndarray):
            if crs is None:
                raise TypeError("if dataset is of type np.ndarray crs must not be None")
            if transform is None:
                raise TypeError("if dataset is of type np.ndarray transform must not be None")
            if dimorder == "first":
                self.__arr = data
            else:
                self.__arr = rasterio.plot.reshape_as_raster(data)

            if self.__arr.ndim == 2:
                self.__arr = np.expand_dims(self.__arr, 0)  # always return 3D for consistency

            self.dataset = None
            self.__update_dataset(crs, transform, nodata=nodata)
        else:
            raise TypeError("dataset must be of type rasterio.io.DatasetReader, str or np.ndarray")

    def __enter__(self):
        return self

    @property
    def arr(self):
        """array property"""
        if self.dimorder == "first":
            return self.__arr
        else:
            return rasterio.plot.reshape_as_image(self.__arr)

    @arr.setter
    def arr(self, arr_altered):
        """Alters the array.
        :param arr_altered: altered array of same dimension order (first or last) and same shape (xy) as original array
        """
        if not isinstance(arr_altered, np.ndarray):
            raise TypeError("altered array must be of type np.ndarray")

        if self.dimorder == "last":
            arr_altered = rasterio.plot.reshape_as_raster(arr_altered)

        if not arr_altered.shape[-2:] == self.__arr.shape[-2:]:
            raise ValueError(
                "Shape mismatch. Shape of source array: {}, shape of altered array {}".format(
                    self.__arr.shape, arr_altered.shape
                )
            )

        self.__arr = arr_altered

    def get_valid_data_bbox(self, nodata=0):
        """bounding box covering the input array's valid data pixels.

        :param nodata: nodata value, optional (default: 0)
        :return: tuple with valid data bounds
        """
        valid_data_window = rasterio.windows.get_data_window(self.__arr, nodata=nodata)
        return rasterio.windows.bounds(valid_data_window, self.dataset.transform)

    def mask(self, bbox, crop=True, pad=False, fill=False, mode="constant", constant_values=0):
        """Mask raster to bbox.

        :param bbox: bounding box of type tuple or Shapely Polygon
        :param crop: bool, see rasterio.mask. Optional, (default: True)
        :param pad: deprecated
        :param fill: enforce raster to cover bbox. if raster extent is smaller than bbox it will be filled according to
            mode and constant_values parameters. Optional (default: False)
        :param mode: str, how to fill, see rasterio.pad. Optional (default: 'constant')
        :param constant_values: nodata value, padding should be filled with, optional (default: 0)
        """
        if pad:
            from warnings import warn

            warn("`pad` was renamed to `fill` in `mask()` and will be removed with version 0.7.0", DeprecationWarning)
            fill = pad

        # TODO https://github.com/mapbox/rasterio/issues/995
        if fill:
            pad_width = self._get_pad_width(bbox)
            if pad_width > 0:
                # only pad raster if it is smaller than bbox
                self.pad(pad_width, mode, constant_values)

        if isinstance(bbox, shapely.geometry.polygon.Polygon):
            self.__arr, transform = rasterio.mask.mask(self.dataset, [bbox], crop=crop)
        elif isinstance(bbox, tuple):
            self.__arr, transform = rasterio.mask.mask(self.dataset, [shapely.geometry.box(*bbox)], crop=crop)
        else:
            raise TypeError(f"bbox must be of type tuple or Shapely Polygon")

        self.__update_dataset(self.dataset.crs, transform, nodata=self.dataset.nodata)

    def _get_pad_width(self, bbox):
        """Calculates biggest difference from raster bounds to bbox. Can be used with pad() to fill array with
        nodata values before masking in case bbox only partially overlaps dataset bounds.

        :param bbox: bounding box of type tuple or Shapely Polygon.
        :return: pad width in pixels, int.
        """
        if isinstance(bbox, shapely.geometry.polygon.Polygon):
            bbox = bbox.bounds
        elif isinstance(bbox, tuple):
            pass
        else:
            raise TypeError(f"bbox must be of type tuple or Shapely Polygon")

        max_diff_ur = np.max(np.subtract(bbox[2:], tuple(self.dataset.bounds[2:])))
        max_diff_ll = np.max(np.subtract(tuple(self.dataset.bounds[:2]), bbox[:2]))
        max_diff = max(max_diff_ll, max_diff_ur)  # buffer in units

        return math.ceil(max_diff / self.dataset.transform.to_gdal()[1])  # units / pixel_size

    def pad(self, pad_width, mode="constant", constant_values=0):
        """Pad raster in all directions.

        :param pad_width: pad width in pixels, int.
        :param mode: str, how to pad, see rasterio.pad. Optional (default: 'constant')
        :param constant_values: nodata value, padding should be filled with, optional (default: 0)
        :return: closed, buffered dataset in memory
        """
        destination = np.zeros(
            (
                self.dataset.count,
                self.__arr.shape[1] + 2 * pad_width,
                self.__arr.shape[2] + 2 * pad_width,
            ),
            self.__arr.dtype,
        )

        for i in range(0, self.dataset.count):
            destination[i], transform = rasterio.pad(
                self.__arr[i],
                self.dataset.transform,
                pad_width,
                mode,
                constant_values=constant_values,
            )

        self.__arr = destination
        self.__update_dataset(self.dataset.crs, transform, nodata=self.dataset.nodata)

    def __update_dataset(self, crs, transform, nodata=None):
        """Update dataset without writing to file after it theoretically changed.

        :param crs: crs of the dataset
        :param transform: transform of the dataset
        :param nodata: nodata value, optional
        :return: file in memory, open as dataset
        """

        meta = {
            "driver": "GTiff",
            "dtype": self.__arr.dtype,
            "nodata": nodata,
            "height": self.__arr.shape[-2],
            "width": self.__arr.shape[-1],
            "count": self.__arr.shape[0],
            "crs": crs,
            "transform": transform,
        }

        memfile = MemoryFile()
        with memfile.open(**meta) as ds:
            ds.write(self.__arr)
        self.dataset = memfile.open()
        memfile.close()

    def warp(self, dst_crs, resampling_method=0, num_threads=4, resolution=None, nodata=None, target_align=None):
        """Reproject a source raster to a destination raster.

        :param dst_crs: CRS or dict, Target coordinate reference system.
        :param resampling_method: Resampling algorithm, int, defaults to 0 (Nearest)
            numbers: https://github.com/mapbox/rasterio/blob/master/rasterio/enums.py#L28
        :param num_threads: int, number of workers, optional (default: 4)
        :param resolution: tuple (x resolution, y resolution) or float, optional.
            Target resolution, in units of target coordinate reference system.
        :param target_align: raster to which to align resolution, extent and gridspacing, optional (Image).
        :param nodata: nodata value of source, int or float, optional.
        """
        if target_align:
            transform = target_align.dataset.transform
            width = target_align.dataset.width
            height = target_align.dataset.height

        else:
            if resolution:
                transform, width, height = rasterio.warp.calculate_default_transform(
                    self.dataset.crs,
                    dst_crs,
                    self.dataset.width,
                    self.dataset.height,
                    *self.dataset.bounds,
                    resolution=resolution,
                )
            else:
                transform, width, height = rasterio.warp.calculate_default_transform(
                    self.dataset.crs,
                    dst_crs,
                    self.dataset.width,
                    self.dataset.height,
                    *self.dataset.bounds,
                )

        destination = np.zeros((self.dataset.count, height, width), self.__arr.dtype)

        self.__arr, transform = rasterio.warp.reproject(
            source=self.__arr,
            destination=destination,
            src_transform=self.dataset.transform,
            src_crs=self.dataset.crs,
            src_nodata=nodata,
            dst_transform=transform,
            dst_crs=dst_crs,
            dst_nodata=nodata,
            resampling=resampling_method,
            num_threads=num_threads,
        )

        self.__update_dataset(dst_crs, transform, nodata=nodata)

    def dn2toa(self, platform, mtl_file=None, wavelengths=None):
        """This method converts digital numbers to top of atmosphere reflectance, like described here:
        https://www.usgs.gov/land-resources/nli/landsat/using-usgs-landsat-level-1-data-product

        :param platform: image platform, possible Platform.Landsat[5, 7, 8] or Platform.Sentinel2 (<enum 'Platform'>).
        :param mtl_file: path to Landsat MTL file that holds the band specific rescale factors (str).
        :param wavelengths: like ["Blue", "Green", "Red", "NIR", "SWIR1", "TIRS", "SWIR2"] for Landsat-5 (list of str).
        """
        if platform in [
            Platform.Landsat5,
            Platform.Landsat7,
            Platform.Landsat8,
        ]:
            if mtl_file is None:
                raise AttributeError(f"'mtl_file' has to be set if platform is {platform}.")
            else:
                # get rescale factors from mtl file
                mtl = toa_utils._load_mtl(str(mtl_file))  # no obvious reason not to call this
                metadata = mtl["L1_METADATA_FILE"]
                sun_elevation = metadata["IMAGE_ATTRIBUTES"]["SUN_ELEVATION"]
                toa = []

                for idx, b in enumerate(self._lookup_bands(platform, wavelengths)):
                    if (platform == Platform.Landsat8 and b in ["10", "11"]) or (
                        platform != Platform.Landsat8 and b.startswith("6")
                    ):
                        if platform == Platform.Landsat8:
                            thermal_conversion_constant1 = metadata["TIRS_THERMAL_CONSTANTS"][f"K1_CONSTANT_BAND_{b}"]
                            thermal_conversion_constant2 = metadata["TIRS_THERMAL_CONSTANTS"][f"K2_CONSTANT_BAND_{b}"]
                        else:
                            thermal_conversion_constant1 = metadata["THERMAL_CONSTANTS"][f"K1_CONSTANT_BAND_{b}"]
                            thermal_conversion_constant2 = metadata["THERMAL_CONSTANTS"][f"K2_CONSTANT_BAND_{b}"]
                        multiplicative_rescaling_factors = metadata["RADIOMETRIC_RESCALING"][f"RADIANCE_MULT_BAND_{b}"]
                        additive_rescaling_factors = metadata["RADIOMETRIC_RESCALING"][f"RADIANCE_ADD_BAND_{b}"]

                        # rescale thermal bands
                        toa.append(
                            brightness_temp.brightness_temp(
                                self.__arr[idx, :, :],
                                ML=multiplicative_rescaling_factors,
                                AL=additive_rescaling_factors,
                                K1=thermal_conversion_constant1,
                                K2=thermal_conversion_constant2,
                            )
                        )
                        continue

                    # rescale reflectance bands
                    multiplicative_rescaling_factors = metadata["RADIOMETRIC_RESCALING"][f"REFLECTANCE_MULT_BAND_{b}"]
                    additive_rescaling_factors = metadata["RADIOMETRIC_RESCALING"][f"REFLECTANCE_ADD_BAND_{b}"]
                    toa.append(
                        reflectance.reflectance(
                            self.__arr[idx, :, :],
                            MR=multiplicative_rescaling_factors,
                            AR=additive_rescaling_factors,
                            E=sun_elevation,
                        )
                    )

                self.__arr = np.array(np.stack(toa, axis=0))
        elif platform == Platform.Sentinel2:
            self.__arr = self.__arr.astype(np.float32) / 10000.0
        else:
            raise AttributeError(
                f"Cannot convert dn2toa. Platform {platform} not supported [Landsat-5, Landsat-7, Landsat-8, "
                f"Sentinel-2]. "
            )

        self.__update_dataset(self.dataset.crs, self.dataset.transform, nodata=self.dataset.nodata)

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
                "pan": "8",
            },
            Platform.Landsat8: {
                "aerosol": "1",
                "blue": "2",
                "green": "3",
                "red": "4",
                "nir": "5",
                "swir1": "6",
                "swir2": "7",
                "pan": "8",
                "cirrus": "9",
                "tirs1": "10",
                "tirs2": "11",
            },
        }

        return [wave_bands[platform][wavelength.lower()] for wavelength in wavelengths]

    def get_tiles(self, width=256, height=256, overlap=0):
        """Calculates rasterio.windows.Window, idea from https://stackoverflow.com/a/54525931

        :param width: int, optional (default: 256). Tile size in pixels.
        :param height: int, optional (default: 256). Tile size in pixels.
        :param overlap: int, optional (default: 0). Overlap in pixels.
        :yields: window of tile
        """
        rows = self.__arr.shape[-2]
        cols = self.__arr.shape[-1]
        offsets = product(range(0, cols, width), range(0, rows, height))
        bounding_window = rasterio.windows.Window(col_off=0, row_off=0, width=cols, height=rows)
        for col_off, row_off in offsets:
            yield rasterio.windows.Window(
                col_off=col_off - overlap,
                row_off=row_off - overlap,
                width=width + 2 * overlap,
                height=height + 2 * overlap,
            ).intersection(
                bounding_window
            )  # clip off window parts not in original array

    def get_subset(self, tile, band=0):
        """Get slice of array.

        :param tile: rasterio.windows.Window tile from get_tiles().
        :param band: Band number (default: 0).
        :return: Sliced numpy array, bounding box of array slice.
        """
        # access window bounds
        bounds = rasterio.windows.bounds(tile, self.dataset.transform)
        return self.__arr[(band,) + tile.toslices()], bounds  # Shape of array is announced with (bands, height, width)

    def to_dask_array(self, chunk_size=(1, 6000, 6000)):
        """transforms numpy to dask array

        :param chunk_size: tuple, size of chunk, optional (default: (1, 6000, 6000))
        :return: dask array
        """
        try:
            import dask.array as da
        except ImportError:
            raise ImportError("to_dask_array requires optional dependency dask[array].")

        self.da_arr = da.from_array(self.__arr, chunks=chunk_size)
        return self.da_arr

    def write_to_file(self, path_to_file, dtype, driver="GTiff", nodata=None, compress=None, kwargs=None):
        """
        Write a dataset to file.
        :param path_to_file: str, path to new file
        :param dtype: datatype, like np.uint16, 'float32' or 'min' to use the minimum type to represent values

        :param driver: str, optional (default: 'GTiff')
        :param nodata: nodata value, e.g. 255 (default: None, means nodata value of dataset will be used)
        :param compress: compression, e.g. 'lzw' (default: None)
        :param kwargs: driver specific keyword arguments, e.g. {'nbits': 1, 'tiled': True} for GTiff (default: None)
            for more keyword arguments see gdal driver specifications, e.g. https://gdal.org/drivers/raster/gtiff.html
        """
        if type(dtype) == str and dtype == "min":
            dtype = rasterio.dtypes.get_minimum_dtype(self.__arr)

        profile = self.dataset.meta
        profile.update(
            {
                "driver": driver,
                "height": self.__arr.shape[-2],
                "width": self.__arr.shape[-1],
                "dtype": dtype,
                "transform": self.dataset.transform,
                "crs": self.dataset.crs,
            }
        )

        if nodata:
            profile.update({"nodata": nodata})

        if compress:
            profile.update({"compress": compress})

        if kwargs:
            profile.update(**kwargs)

        with rasterio.open(path_to_file, "w", **profile) as dst:
            dst.write(self.__arr.astype(dtype))

    def close(self):
        """closes Image"""
        self.dataset.close()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
