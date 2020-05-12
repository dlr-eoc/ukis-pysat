import os
import unittest

import dask.array
import numpy as np
from rasterio import windows
from rasterio.coords import BoundingBox
from shapely.geometry import box

from ukis_pysat.members import Platform
from ukis_pysat.data import Image

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
            BoundingBox(left=11.896863892, bottom=51.446545369, right=11.9578595, top=51.515176657,),
        )

        img.mask_image((11.9027457562112939, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,))
        self.assertEqual(
            img.dataset.bounds,
            BoundingBox(left=11.896863892, bottom=51.446545369, right=11.9578595, top=51.515176657,),
        )

        img.mask_image(
            box(11.8919236802142620, 51.4664152338322580, 11.9477435281016131, 51.5009522690838750,), pad=True,
        )
        self.assertEqual(
            img.dataset.bounds,
            BoundingBox(
                left=11.897762207287187, bottom=51.4614574027801, right=11.952739102863033, top=51.50592400953403,
            ),
        )

    def test_warp(self):
        self.assertEqual(img.crs, "EPSG:4326")

        img.warp("EPSG:3857")
        self.assertEqual(img.crs, "EPSG:3857")

        img.warp("EPSG:4326", resolution=1.0)
        self.assertEqual(1.0, img.transform.to_gdal()[1])

    def test_dn2toa(self):
        # TODO add more testcases
        self.assertLogs(img.dn2toa(Platform.Sentinel1), level="WARNING")

    def test__lookup_bands(self):
        self.assertEqual(
            ["1", "2", "3"], img._lookup_bands(Platform.Landsat5, ["Blue", "Green", "Red"]),
        )
        self.assertEqual(
            ["9", "10", "11"], img._lookup_bands(Platform.Landsat8, ["PAN", "Tirs1", "Tirs2"]),
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
                self.assertEqual(array, np.zeros(shape=(1, 7, 7)))
                self.assertEqual(bounds, (11.903960582768779, 51.45624717410995, 11.904589403469808, 51.45687599481152))

    def test_get_dask_array(self):
        self.assertIsInstance(img.get_dask_array(chunk_size=(1, 10, 10)), dask.array.core.Array)

    def test_write_to_file(self):
        img.write_to_file(r"result.tif")
        img2 = Image("result.tif")
        self.assertTrue(np.array_equal(img2.arr, img.arr))

        img2.close()
        os.remove(r"result.tif")


if __name__ == "__main__":
    unittest.main()
