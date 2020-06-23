# -*- coding: utf-8 -*-

import math
from itertools import product

from ukis_pysat.members import Platform

try:
    import numpy as np
    import rasterio
    import rasterio.mask
    from rasterio import windows
    from rasterio.dtypes import get_minimum_dtype
    from rasterio.io import MemoryFile
    from rasterio.plot import reshape_as_image, reshape_as_raster
    from rasterio.warp import calculate_default_transform, reproject
    from rio_toa import reflectance, brightness_temp, toa_utils
    from shapely.geometry import box, polygon
except ImportError as e:
    msg = (
        "ukis_pysat.raster dependencies are not installed.\n\n"
        "Please pip install as follows:\n\n"
        "  python -m pip install ukis-pysat[raster] --upgrade"
    )
    raise ImportError(str(e) + "\n\n" + msg)


class Image:

    da_arr = None

    def __init__(self, data, dimorder="first", crs=None, transform=None):
        """
        :param data: rasterio.io.DatasetReader or path to raster or np.ndarray of shape (bands, rows, columns)
        :param dimorder: Order of channels or bands 'first' or 'last' (default: 'first')
        :param crs: Coordinate reference system used when creating form array. If 'data' is np.ndarray this is reqired (default: None) 
        :param transform: Affine transformation mapping the pixel space to geographic space. If 'data' is np.ndarray this is reqired (default:None) 
        """
        if dimorder in ("first", "last"):
            self.dimorder = dimorder
        else:
            raise TypeError("dimorder for bands or channels must be either 'first' or 'last'.")
        try:
            self.dataset = rasterio.open(data)
            self.crs = self.dataset.crs
            self.transform = self.dataset.transform
            self.__arr = self.dataset.read()
        except (TypeError, AttributeError):
            if isinstance(data, rasterio.io.DatasetReader):
                self.dataset = data
                self.crs = self.dataset.crs
                self.transform = self.dataset.transform
                self.__arr = self.dataset.read()
            elif isinstance(data, np.ndarray):
                if crs is None:
                    raise TypeError("if dataset is of type np.ndarray crs must not be None")
                if transform is None:
                    raise TypeError("if dataset is of type np.ndarray transform must not be None")
                meta = {"dtype": data.dtype, "count": data.shape[0], "crs": crs, "driver": "GTiff"}
                self.__arr = data
                self.transform = transform
                self.dataset = self.__update_dataset(meta).open()
                self.crs = self.dataset.crs
                self.transform = self.dataset.transform
            else:
                raise TypeError("dataset must be of type str, rasterio.io.DatasetReader or np.ndarray")

    @property
    def arr(self):
        """array property"""
        if self.dimorder == "first":
            return self.__arr
        elif self.dimorder == "last":
            return reshape_as_image(self.__arr)
        else:
            raise AttributeError("dimorder for bands or channels must be either 'first' or 'last'.")

    def get_valid_data_bbox(self, nodata=0):
        """bounding box covering the input array's valid data pixels.

        :param nodata: nodata value, optional (default: 0)
        :return: tuple with valid data bounds
        """
        valid_data_window = windows.get_data_window(self.__arr, nodata=nodata)
        return windows.bounds(valid_data_window, windows.transform(valid_data_window, self.transform))

    def mask_image(self, bbox, crop=True, pad=False, mode="constant", constant_values=0):
        """Mask the area outside of the input shapes with no data.

        :param bbox: bounding box of type tuple or Shapely Polygon
        :param crop: bool, see rasterio.mask. Optional, (default: True)
        :param pad: pads image, should only be used when bbox.bounds extent img.bounds, optional (default: False)
        :param mode: str, how to pad, see rasterio.pad. Optional (default: 'constant') 
        :param constant_values: nodata value, padding should be filled with, optional (default: 0)
        """
        # TODO https://github.com/mapbox/rasterio/issues/995
        if pad:
            self.dataset = self._pad_to_bbox(bbox, mode, constant_values).open()

        if isinstance(bbox, polygon.Polygon):
            self.__arr, self.transform = rasterio.mask.mask(self.dataset, [bbox], crop=crop)
        elif isinstance(bbox, tuple):
            self.__arr, self.transform = rasterio.mask.mask(self.dataset, [box(*bbox)], crop=crop)
        else:
            raise TypeError(f"bbox must be of type tuple or Shapely Polygon")

        # update for further processing
        self.dataset = self.__update_dataset(self.dataset.meta).open()

    def _pad_to_bbox(self, bbox, mode="constant", constant_values=0):
        """Buffers array with biggest difference to bbox and adjusts affine transform matrix. Can be used to fill
        array with nodata values before masking in case bbox only partially overlaps dataset bounds.

        :param bbox: bounding box of type tuple or Shapely Polygon
        :param mode: str, how to pad, see rasterio.pad. Optional (default: 'constant')
        :param constant_values: nodata value, padding should be filled with, optional (default: 0)
        :return: closed, buffered dataset in memory
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
            (self.dataset.count, self.__arr.shape[1] + 2 * pad_width, self.__arr.shape[2] + 2 * pad_width,),
            self.__arr.dtype,
        )

        for i in range(0, self.dataset.count):
            destination[i], self.transform = rasterio.pad(
                self.__arr[0], self.transform, pad_width, mode, constant_values=constant_values,
            )

        self.__arr = destination

        return self.__update_dataset(self.dataset.meta)

    def __update_dataset(self, meta):
        """Update dataset without writing to file after it theoretically changed.

        :param meta: The basic metadata of the dataset as returned from the meta property of rasterio Datasets 

        :return: closed dataset in memory
        """
        arr = self.__arr
        meta.update(
            {"height": self.__arr.shape[-2], "width": self.__arr.shape[-1], "transform": self.transform,}
        )

        memfile = MemoryFile()
        ds = memfile.open(**meta)
        ds.write(self.__arr)

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

        destination = np.zeros((self.dataset.count, height, width), self.__arr.dtype)

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
        self.__arr = destination
        self.transform = transform
        self.crs = dst_crs
        self.dataset = self.__update_dataset(self.dataset.meta).open()

    def dn2toa(self, platform, mtl_file=None, wavelengths=None):
        """This method converts digital numbers to top of atmosphere reflectance, like described here:
        https://www.usgs.gov/land-resources/nli/landsat/using-usgs-landsat-level-1-data-product

        :param platform: image platform, possible Platform.Landsat[5, 7, 8] or Platform.Sentinel2 (<enum 'Platform'>).
        :param mtl_file: path to Landsat MTL file that holds the band specific rescale factors (str).
        :param wavelengths: like ["Blue", "Green", "Red", "NIR", "SWIR1", "TIRS", "SWIR2"] for Landsat-5 (list of str).
        """
        # TODO rio-toa does not seem to be maintained anymore
        if platform in [
            Platform.Landsat5,
            Platform.Landsat7,
            Platform.Landsat8,
        ]:
            if mtl_file is None:
                raise AttributeError(f"'mtl_file' has to be set if platform is {platform}.")
            else:
                # get rescale factors from mtl file
                mtl = toa_utils._load_mtl(mtl_file)  # no obvious reason not to call this
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

        TODO boundless with 'reflect' padding

        :param width: int, optional (default: 256). Tile size in pixels.
        :param height: int, optional (default: 256). Tile size in pixels.
        :param overlap: int, optional (default: 0). Overlap in pixels.
        :yields: window of tile
        """
        rows = self.__arr.shape[-2]
        cols = self.__arr.shape[-1]
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

    def get_subset(self, tile, band=0):
        """Get slice of array.

        :param tile: rasterio.windows.Window tile from get_tiles().
        :param band: Band number (default: 0).
        :return: Sliced numpy array, bounding box of array slice.
        """
        # access window bounds
        bounds = windows.bounds(tile, self.dataset.transform)
        return self.__arr[(band,) + tile.toslices()], bounds  # Shape of array is announced with (bands, height, width)

    def to_dask_array(self, chunk_size=(1, 6000, 6000)):
        """ transforms numpy to dask array

        :param chunk_size: tuple, size of chunk, optional (default: (1, 6000, 6000))
        :return: dask array
        """
        try:
            import dask.array as da
        except ImportError:
            raise ImportError("to_dask_array requires optional dependency dask[array].")

        self.da_arr = da.from_array(self.__arr, chunks=chunk_size)
        return self.da_arr

    def write_to_file(self, path_to_file, dtype, driver="GTiff", nodata=None, compress=None):
        """
        Write a dataset to file.
        :param path_to_file: str, path to new file
        :param dtype: datatype, like np.uint16, 'float32' or 'min' to use the minimum type to represent values

        :param driver: str, optional (default: 'GTiff')
        :param nodata: nodata value, e.g. 255 (default: None, means nodata value of dataset will be used)
        :param compress: compression, e.g. 'lzw' (default: None)
        """
        if dtype == "min":
            dtype = get_minimum_dtype(self.__arr)

        profile = self.dataset.meta
        profile.update(
            {
                "driver": driver,
                "height": self.__arr.shape[-2],
                "width": self.__arr.shape[-1],
                "dtype": dtype,
                "transform": self.transform,
                "crs": self.crs,
            }
        )

        if nodata:
            profile.update({"nodata": nodata})

        if compress:
            profile.update({"compress": compress})

        with rasterio.open(path_to_file, "w", **profile) as dst:
            dst.write(self.__arr.astype(dtype))

    def close(self):
        """closes Image"""
        self.dataset.close()
