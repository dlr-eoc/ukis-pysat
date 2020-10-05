#!/usr/bin/env python3
import os
import unittest
from pathlib import Path

import dask.array
import numpy as np
from rasterio import windows
from rasterio.coords import BoundingBox
from rasterio.transform import from_bounds
from shapely.geometry import box
from ukis_pysat.members import Platform
from ukis_pysat.raster import Image

TEST_FILE = Path(__file__).parents[0] / "testfiles" / "dummy.tif"


class DataTest(unittest.TestCase):
    def setUp(self):
        self.img = Image(TEST_FILE)

    def tearDown(self):
        self.img.close()

    def test_init(self):
        with Image(self.img.dataset) as img:
            self.assertTrue(np.array_equal(self.img.arr, img.arr))

    def test_context(self):
        with Image(TEST_FILE) as raster_file:
            self.assertTrue(np.array_equal(self.img.arr, raster_file.arr))

    def test_init_fail_invalid_path(self):
        with self.assertRaises(TypeError):
            Image(1)

    def test_init_fail_invalid_dataset(self):
        with self.assertRaises(TypeError,):
            Image(1)

    def test_init_with_arry_fail_missing_crs_and_transform(self):
        with self.assertRaises(TypeError):
            Image(data=self.img.arr)

    def test_init_with_arry_fail_missing_transform(self):
        with self.assertRaises(TypeError):
            Image(data=self.img.arr, crs=self.img.dataset.crs)

    def test_init_with_array(self):
        img = Image(self.img.arr, crs=self.img.dataset.crs, transform=self.img.dataset.transform)
        self.assertTrue(np.array_equal(self.img.arr, img.arr))
        img.close()

    def test_init_2dim(self):
        with Image(np.ones(shape=(385, 502)), crs=self.img.dataset.crs, transform=self.img.dataset.transform) as img:
            self.assertEqual(img.arr.ndim, 3)
            self.assertEqual(len(img.arr), 1)
            self.assertEqual(img.arr.shape, (1, 385, 502))

    def test_init_with_arry_fail_missing_crs(self):
        with self.assertRaises(TypeError):
            Image(data=self.img.arr, crs=self.img.dataset.transform)

    def test_dimorder_error(self):
        with self.assertRaises(TypeError):
            Image(TEST_FILE, dimorder="middle")

    def test_arr(self):
        img_first = Image(TEST_FILE, dimorder="first")
        img_first.mask(box(11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(img_first.arr.shape, (1, 385, 502))
        self.assertEqual(
            str(img_first.dataset.transform),
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
        img_first.close()

        img_last = Image(TEST_FILE, dimorder="last")
        img_last.mask(box(11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(img_last.arr.shape, (385, 502, 1))
        self.assertEqual(
            str(img_last.dataset.transform),
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
        img_last.close()

        img_first = Image(
            np.ones((1, 385, 502)), dimorder="first", crs=self.img.dataset.crs, transform=self.img.dataset.transform
        )
        self.assertEqual(img_first.arr.shape, (1, 385, 502))
        img_first.close()

        img_last = Image(
            np.ones((385, 502, 1)), dimorder="last", crs=self.img.dataset.crs, transform=self.img.dataset.transform
        )
        self.assertEqual(img_last.arr.shape, (385, 502, 1))
        img_last.close()

    def test_arr_nodata(self):
        array = np.ones((3, 385, 502))

        with Image(array, crs=self.img.dataset.crs, transform=self.img.dataset.transform, nodata=0.0) as img_nodata:
            self.assertEqual(img_nodata.dataset.nodata, 0.0)
            self.assertEqual(img_nodata.dataset.nodatavals, (0.0, 0.0, 0.0))

    def test_set_array(self):
        with Image(TEST_FILE, dimorder="last") as im:
            np.putmask(im.arr, im.arr > 0, 0)
            im.arr = im.arr + 1

            self.assertTrue(np.array_equal(im.arr, np.ones(shape=im.arr.shape)))

    def test_set_array_error(self):
        img_first = Image(TEST_FILE, dimorder="first")

        with self.assertRaises(TypeError):
            img_first.arr = "error"

        with self.assertRaises(ValueError):
            img_first.arr = np.ones(shape=(764, 679, 1))

        with self.assertRaises(ValueError):
            img_last = Image(TEST_FILE, dimorder="last")
            img_last.arr = np.ones(shape=(1, 764, 679))

    def test_get_valid_data_bbox(self):
        self.assertEqual(
            self.img.get_valid_data_bbox(nodata=0.0),
            (11.898660522574374, 51.51158339584816, 11.900457153148748, 51.51338002642408),
        )

    def test_mask_image(self):
        with self.assertRaises(TypeError, msg="bbox must be of type tuple or Shapely Polygon"):
            self.img.mask([1, 2, 3])

        self.img.mask(box(11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(
            self.img.dataset.bounds,
            BoundingBox(
                left=11.902702941366716, bottom=51.46639813686387, right=11.947798368783504, top=51.50098327545026,
            ),
        )

        self.img.mask((11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(
            self.img.dataset.bounds,
            BoundingBox(
                left=11.902702941366716, bottom=51.46639813686387, right=11.947798368783504, top=51.50098327545026,
            ),
        )

        self.img.mask(
            box(11.8919236802142620, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,), fill=True,
        )
        self.assertEqual(
            self.img.dataset.bounds,
            BoundingBox(
                left=11.891923157920472, bottom=51.46639813686387, right=11.947798368783504, top=51.50098327545026
            ),
        )

    def test_warp(self):
        self.assertEqual(self.img.dataset.crs, "EPSG:4326")

        self.img.warp("EPSG:3857")
        self.assertEqual(self.img.dataset.crs, "EPSG:3857")
        self.assertEqual(self.img.dataset.meta["crs"], "EPSG:3857")

        self.img.warp("EPSG:4326", resolution=1.0)
        self.assertEqual(1.0, self.img.dataset.transform.to_gdal()[1])

        source_img = Image(TEST_FILE)
        source_img.warp("EPSG:3857", resolution=10)
        target_img = Image(TEST_FILE)
        target_img.warp("EPSG:3857", resolution=25)
        self.assertNotEqual(source_img.dataset.transform, target_img.dataset.transform)
        source_img.warp("EPSG:3857", target_align=target_img)
        self.assertEqual(source_img.dataset.transform, target_img.dataset.transform)

    def test_dn2toa(self):
        target_dir = Path(__file__).parents[0] / "testfiles" / "satellite_data"
        tests = [
            {
                "platform": Platform.Landsat8,
                "dn_file": target_dir.joinpath("LC08_L1TP_193024_20200509_20200509_01_RT.tif"),
                "toa_file": target_dir.joinpath("LC08_L1TP_193024_20200509_20200509_01_RT_toa.tif"),
                "mtl_file": target_dir.joinpath("LC08_L1TP_193024_20200509_20200509_01_RT_MTL.txt"),
                "wavelengths": ["Aerosol", "Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "Cirrus", "TIRS1", "TIRS2"],
            },
            {
                "platform": Platform.Landsat7,
                "dn_file": target_dir.joinpath("LE07_L1TP_193024_20100420_20161215_01_T1.tif"),
                "toa_file": target_dir.joinpath("LE07_L1TP_193024_20100420_20161215_01_T1_toa.tif"),
                "mtl_file": target_dir.joinpath("LE07_L1TP_193024_20100420_20161215_01_T1_MTL.txt"),
                "wavelengths": ["Blue", "Green", "Red", "NIR", "SWIR1", "TIRS1", "TIRS2", "SWIR2"],
            },
            {
                "platform": Platform.Landsat5,
                "dn_file": target_dir.joinpath("LT05_L1TP_193024_20050516_20161127_01_T1.tif"),
                "toa_file": target_dir.joinpath("LT05_L1TP_193024_20050516_20161127_01_T1_toa.tif"),
                "mtl_file": target_dir.joinpath("LT05_L1TP_193024_20050516_20161127_01_T1_MTL.txt"),
                "wavelengths": ["Blue", "Green", "Red", "NIR", "SWIR1", "TIRS", "SWIR2"],
            },
            {
                "platform": Platform.Sentinel2,
                "dn_file": target_dir.joinpath("S2B_MSIL1C_20200406T101559_N0209_R065_T32UPC_20200406T130159.tif"),
                "toa_file": target_dir.joinpath("S2B_MSIL1C_20200406T101559_N0209_R065_T32UPC_20200406T130159_toa.tif"),
                "mtl_file": None,
                "wavelengths": None,
            },
        ]

        for i in range(len(tests)):
            img_dn = Image(tests[i]["dn_file"])
            img_toa = Image(tests[i]["toa_file"])
            img_dn.dn2toa(
                platform=tests[i]["platform"], mtl_file=tests[i]["mtl_file"], wavelengths=tests[i]["wavelengths"]
            )

            self.assertTrue(np.array_equal(img_dn.arr, img_toa.arr))
            img_dn.close()
            img_toa.close()

        with self.assertRaises(AttributeError, msg=f"'mtl_file' has to be set if platform is {Platform.Landsat8}."):
            self.img.dn2toa(platform=Platform.Landsat8)

        with self.assertRaises(
            AttributeError,
            msg=f"Cannot convert dn2toa. Platform {Platform.Sentinel1} not "
            f"supported [Landsat-5, Landsat-7, Landsat-8, Sentinel-2]. ",
        ):
            self.img.dn2toa(platform=Platform.Sentinel1)

    def test__lookup_bands(self):
        self.assertEqual(
            ["1", "2", "3"], self.img._lookup_bands(Platform.Landsat5, ["Blue", "Green", "Red"]),
        )
        self.assertEqual(
            ["8", "10", "11"], self.img._lookup_bands(Platform.Landsat8, ["PAN", "Tirs1", "Tirs2"]),
        )

    def test_get_tiles(self):
        for idx, each in enumerate(self.img.get_tiles(5, 5, 1)):
            self.assertIsInstance(each, windows.Window)
            if idx == 2578:
                self.assertEqual(each, windows.Window(col_off=79, row_off=649, width=7, height=7))

        self.assertEqual(idx, 20807)

    def test_get_subset(self):
        for idx, each in enumerate(self.img.get_tiles(5, 5, 1)):
            if idx == 2578:
                array, bounds = self.img.get_subset(each)
                self.assertTrue(np.array_equal(array, np.zeros(shape=(7, 7), dtype=array.dtype)))
                self.assertEqual(bounds, (11.903960582768779, 51.45624717410995, 11.904589403469808, 51.45687599481152))

    def test_get_dask_array(self):
        self.assertIsInstance(self.img.to_dask_array(chunk_size=(1, 10, 10)), dask.array.core.Array)

    def test_write_to_file(self):
        self.img.write_to_file(r"result.tif", np.uint16)
        with Image("result.tif") as img2:
            self.assertTrue(np.array_equal(img2.arr, self.img.arr))

        os.remove(r"result.tif")

        self.img.write_to_file(r"result.tif", "min", compress="lzw")
        with Image("result.tif") as img2:
            self.assertEqual(img2.arr.dtype, "uint8")
            self.assertEqual(img2.dataset.profile["compress"], "lzw")

        os.remove(r"result.tif")

        self.img.write_to_file(r"result.tif", np.uint8, compress="packbits", kwargs={"tiled": True})
        with Image("result.tif") as img2:
            self.assertEqual(img2.arr.dtype, "uint8")
            self.assertEqual(img2.dataset.profile["tiled"], True)

        os.remove(r"result.tif")

        with Image(self.img.arr, crs=self.img.dataset.crs, transform=self.img.dataset.transform) as img3:
            img3.write_to_file(r"result.tif", np.uint16)

        with Image("result.tif") as img4:
            self.assertTrue(np.array_equal(img4.arr, self.img.arr))

        os.remove(r"result.tif")


if __name__ == "__main__":
    unittest.main()
