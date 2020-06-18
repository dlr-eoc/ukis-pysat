import os
import unittest

import dask.array
import numpy as np
from rasterio import windows
from rasterio.coords import BoundingBox
from rasterio.transform import from_bounds
from shapely.geometry import box

from ukis_pysat.members import Platform
from ukis_pysat.raster import Image

img = Image(path=os.path.join(os.path.dirname(__file__), "testfiles", "dummy.tif"))


class DataTest(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(TypeError, msg=f"path must be of type str"):
            Image(path=1)

        with self.assertRaises(
            TypeError, msg=f"dataset must be of type rasterio.io.DatasetReader and arr must be of type numpy.ndarray"
        ):
            Image(dataset=1, arr=img.arr)

        with self.assertRaises(
            TypeError, msg=f"dataset must be of type rasterio.io.DatasetReader and arr must be of type numpy.ndarray"
        ):
            Image(arr=img.arr)

        self.assertTrue(np.array_equal(img.arr, Image(dataset=img.dataset, arr=img.arr).arr))

    def test_arr(self):
        img_first = Image(path=os.path.join(os.path.dirname(__file__), "testfiles", "dummy.tif"), dimorder="first")
        img_first.mask_image(box(11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(img_first.arr.shape, (1, 385, 502))
        self.assertEqual(
            str(img_first.transform),
            str(
                from_bounds(
                    11.9027457562112939,
                    51.4664152338322580,
                    11.9477435281016131,
                    51.5009522690838750,
                    img_first.arr.shape[2],
                    img_first.arr.shape[1],
                )
            ),
        )

        img_last = Image(path=os.path.join(os.path.dirname(__file__), "testfiles", "dummy.tif"), dimorder="last")
        img_last.mask_image(box(11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(img_last.arr.shape, (385, 502, 1))
        self.assertEqual(
            str(img_last.transform),
            str(
                from_bounds(
                    11.9027457562112939,
                    51.4664152338322580,
                    11.9477435281016131,
                    51.5009522690838750,
                    img_last.arr.shape[1],
                    img_last.arr.shape[0],
                )
            ),
        )

        img = Image(path=os.path.join(os.path.dirname(__file__), "testfiles", "dummy.tif"), dimorder="first")
        img_first = Image(dataset=img.dataset, arr=np.ones((1, 385, 502)), dimorder="first")
        self.assertEqual(img_first.arr.shape, (1, 385, 502))

        img_last = Image(dataset=img.dataset, arr=np.ones((385, 502, 1)), dimorder="last")
        self.assertEqual(img_last.arr.shape, (385, 502, 1))

        with self.assertRaises(AttributeError, msg="dimorder for bands or channels must be either 'first' or 'last'."):
            img_first = Image(path=os.path.join(os.path.dirname(__file__), "testfiles", "dummy.tif"), dimorder="middle")
            img_first.arr

    def test_get_valid_data_bbox(self):
        self.assertEqual(
            img.get_valid_data_bbox(), (11.896863892, 51.515176657, 11.896863892, 51.515176657),
        )
        self.assertEqual(
            img.get_valid_data_bbox(nodata=1), (11.896863892, 51.446545369, 11.9578595, 51.515176657),
        )

    def test_mask_image(self):
        with self.assertRaises(TypeError, msg="bbox must be of type tuple or Shapely Polygon"):
            img.mask_image([1, 2, 3])

        img.mask_image(box(11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(
            img.dataset.bounds,
            BoundingBox(
                left=11.902702941366716, bottom=51.46639813686387, right=11.947798368783504, top=51.50098327545026,
            ),
        )

        img.mask_image((11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(
            img.dataset.bounds,
            BoundingBox(
                left=11.902702941366716, bottom=51.46639813686387, right=11.947798368783504, top=51.50098327545026,
            ),
        )

        img.mask_image(
            box(11.8919236802142620, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,), pad=True,
        )
        self.assertEqual(
            img.dataset.bounds,
            BoundingBox(
                left=11.891923157920472, bottom=51.46639813686387, right=11.947798368783504, top=51.50098327545026
            ),
        )

    def test_warp(self):
        self.assertEqual(img.crs, "EPSG:4326")

        img.warp("EPSG:3857")
        self.assertEqual(img.crs, "EPSG:3857")

        img.warp("EPSG:4326", resolution=1.0)
        self.assertEqual(1.0, img.transform.to_gdal()[1])

    def test_dn2toa(self):
        target_dir = os.path.join(os.path.dirname(__file__), "testfiles", "satellite_data")
        tests = [
            {
                "platform": Platform.Landsat8,
                "dn_file": os.path.join(target_dir, "LC08_L1TP_193024_20200509_20200509_01_RT.tif"),
                "toa_file": os.path.join(target_dir, "LC08_L1TP_193024_20200509_20200509_01_RT_toa.tif"),
                "mtl_file": os.path.join(target_dir, "LC08_L1TP_193024_20200509_20200509_01_RT_MTL.txt"),
                "wavelengths": ["Aerosol", "Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "Cirrus", "TIRS1", "TIRS2"],
            },
            {
                "platform": Platform.Landsat7,
                "dn_file": os.path.join(target_dir, "LE07_L1TP_193024_20100420_20161215_01_T1.tif"),
                "toa_file": os.path.join(target_dir, "LE07_L1TP_193024_20100420_20161215_01_T1_toa.tif"),
                "mtl_file": os.path.join(target_dir, "LE07_L1TP_193024_20100420_20161215_01_T1_MTL.txt"),
                "wavelengths": ["Blue", "Green", "Red", "NIR", "SWIR1", "TIRS1", "TIRS2", "SWIR2"],
            },
            {
                "platform": Platform.Landsat5,
                "dn_file": os.path.join(target_dir, "LT05_L1TP_193024_20050516_20161127_01_T1.tif"),
                "toa_file": os.path.join(target_dir, "LT05_L1TP_193024_20050516_20161127_01_T1_toa.tif"),
                "mtl_file": os.path.join(target_dir, "LT05_L1TP_193024_20050516_20161127_01_T1_MTL.txt"),
                "wavelengths": ["Blue", "Green", "Red", "NIR", "SWIR1", "TIRS", "SWIR2"],
            },
            {
                "platform": Platform.Sentinel2,
                "dn_file": os.path.join(target_dir, "S2B_MSIL1C_20200406T101559_N0209_R065_T32UPC_20200406T130159.tif"),
                "toa_file": os.path.join(
                    target_dir, "S2B_MSIL1C_20200406T101559_N0209_R065_T32UPC_20200406T130159_toa.tif"
                ),
                "mtl_file": None,
                "wavelengths": None,
            },
        ]

        for i in range(len(tests)):
            img_dn = Image(path=tests[i]["dn_file"])
            img_toa = Image(path=tests[i]["toa_file"])
            img_dn.dn2toa(
                platform=tests[i]["platform"], mtl_file=tests[i]["mtl_file"], wavelengths=tests[i]["wavelengths"]
            )
            self.assertTrue(np.array_equal(img_dn.arr, img_toa.arr))

        with self.assertRaises(AttributeError, msg=f"'mtl_file' has to be set if platform is {Platform.Landsat8}."):
            img.dn2toa(platform=Platform.Landsat8)

        with self.assertRaises(
            AttributeError,
            msg=f"Cannot convert dn2toa. Platform {Platform.Sentinel1} not "
            f"supported [Landsat-5, Landsat-7, Landsat-8, Sentinel-2]. ",
        ):
            img.dn2toa(platform=Platform.Sentinel1)

    def test__lookup_bands(self):
        self.assertEqual(
            ["1", "2", "3"], img._lookup_bands(Platform.Landsat5, ["Blue", "Green", "Red"]),
        )
        self.assertEqual(
            ["8", "10", "11"], img._lookup_bands(Platform.Landsat8, ["PAN", "Tirs1", "Tirs2"]),
        )

    def test_get_tiles(self):
        for idx, each in enumerate(img.get_tiles(5, 5, 1)):
            self.assertIsInstance(each, windows.Window)
            if idx == 2578:
                self.assertEqual(each, windows.Window(col_off=79, row_off=649, width=7, height=7))

        self.assertEqual(idx, 20807)

    def test_get_subset(self):
        for idx, each in enumerate(img.get_tiles(5, 5, 1)):
            if idx == 2578:
                array, bounds = img.get_subset(each)
                self.assertTrue(np.array_equal(array, np.zeros(shape=(7, 7), dtype=array.dtype)))
                self.assertEqual(bounds, (11.903960582768779, 51.45624717410995, 11.904589403469808, 51.45687599481152))

    def test_get_dask_array(self):
        self.assertIsInstance(img.to_dask_array(chunk_size=(1, 10, 10)), dask.array.core.Array)

    def test_write_to_file(self):
        img.write_to_file(r"result.tif", np.uint16)
        img2 = Image("result.tif")
        self.assertTrue(np.array_equal(img2.arr, img.arr))

        img2.close()
        os.remove(r"result.tif")

        img.write_to_file(r"result.tif", "min", compress="lzw")
        img2 = Image("result.tif")
        self.assertEqual(img2.arr.dtype, "uint8")
        self.assertEqual(img2.dataset.profile["compress"], "lzw")

        img2.close()
        os.remove(r"result.tif")


if __name__ == "__main__":
    unittest.main()
