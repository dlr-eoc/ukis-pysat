import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

import ukis_pysat.file as psf

path_testfiles = Path(__file__).parents[0] / "testfiles"
str_path = os.path.join(os.path.dirname(__file__), "testfiles")


class FileTest(unittest.TestCase):
    def test_env(self):
        with self.assertRaises(KeyError, msg=f"No environment variable Key found"):
            psf.env_get("Key")

        os.environ["FUN"] = "True"
        self.assertTrue(psf.env_get("FUN", boolean=True))
        os.environ["ISITWEEKENDYET"] = "0"
        self.assertFalse(psf.env_get("ISITWEEKENDYET", boolean=True))

    def test_get_sentinel_scene_from_dir(self):
        with psf.get_sentinel_scene_from_dir(path_testfiles) as (full_path, ident):
            self.assertEqual("S1M_hello_from_inside", ident)

        with psf.get_sentinel_scene_from_dir(str_path) as (full_path, ident):
            self.assertEqual("S1M_hello_from_inside", ident)

        with psf.get_sentinel_scene_from_dir(path_testfiles.joinpath("another_scene")) as (full_path, ident):
            self.assertEqual("S2__IN_FOLDER", ident)

    def test_get_polarization_from_s1_filename_1SDH(self):
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_1SDH_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            "HH",
        )
    def test_get_polarization_from_s1_filename_1SSH(self):
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_1SSH_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            "HH",
        )
    def test_get_polarization_from_s1_filename_2SSV(self):
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_2SSV_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            "VV",
        )
    def test_get_polarization_from_s1_filename_1SDV(self):
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_1SDV_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip", True,
            ),
            "VV,VH",
        )

    def test_get_ts_from_sentinel_filename_S3M_TTT(self):
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S3M_OL_L_TTT____20200113T002219_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_i_GGG_c.SEN3"
            ),
            datetime(2020, 1, 13, 0, 22, 19, tzinfo=timezone.utc),
        )
    def test_get_ts_from_sentinel_filename_S1M_2219(self):
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S1M_BB_TTTR_LFPP_YYYYMMDDTHHMMSS_20200113T002219_OOOOOO_DDDDDD_CCCC.SAFE.zip", False,
            ),
            datetime(2020, 1, 13, 0, 22, 19, tzinfo=timezone.utc),
        )
    def test_get_ts_from_sentinel_filename_S1M_4619(self):
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S1M_BB_TTTR_LFPP_20200113T074619_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            datetime(2020, 1, 13, 7, 46, 19, tzinfo=timezone.utc),
        )
    def test_get_ts_from_sentinel_filename_S2AM_2219(self):
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S2AM_MSIXXX_20200113T002219_Nxxyy_ROOO_Txxxxx_<Product Discriminator>.SAFE"
            ),
            datetime(2020, 1, 13, 0, 22, 19, tzinfo=timezone.utc),
        )
    def test_get_ts_from_sentinel_filename_S3M_2219(self):
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S3M_OL_L_TTTTTT_yyyymmddThhmmss_20200113T002219_YYYYMMDDTHHMMSS_i_GGG_c.SEN3", False
            ),
            datetime(2020, 1, 13, 0, 22, 19, tzinfo=timezone.utc),
        )

    def test_get_ESA_date_from_datetime(self):
        self.assertEqual(
            psf.get_sat_ts_from_datetime(datetime(2020, 1, 13, 7, 46, 19, tzinfo=timezone.utc)), "20200113T074619"
        )

    def test_get_footprint_from_manifest(self):
        self.assertEqual(
            psf.get_footprint_from_manifest(path_testfiles.joinpath("manifest.safe")).wkt,
            "POLYGON ((149.766922 -24.439564, 153.728622 -23.51771, 154.075058 -24.737713, 150.077042 "
            "-25.668921, 149.766922 -24.439564))",
        )
        with self.assertRaises(KeyError, msg="Footprint not found"):
            psf.get_footprint_from_manifest(os.path.join(path_testfiles, "manifest_bad.safe"))

    def test_get_origin_from_manifest(self):
        self.assertEqual(
            psf.get_origin_from_manifest(path_testfiles.joinpath("manifest.safe")), "United Kingdom",
        )
        with self.assertRaises(KeyError, msg="Country of origin not found."):
            psf.get_footprint_from_manifest(os.path.join(path_testfiles, "manifest_bad.safe"))

    def test_get_ipf_from_manifest(self):
        self.assertEqual(
            psf.get_ipf_from_manifest(path_testfiles.joinpath("manifest.safe")), 2.82,
        )
        with self.assertRaises(KeyError, msg="IPF Version not found."):
            psf.get_footprint_from_manifest(os.path.join(path_testfiles, "manifest_bad.safe"))

    def test_get_pixel_spacing(self):
        self.assertEqual(psf.get_pixel_spacing(path_testfiles), (40.0, 0.0003593261136478086))
        with self.assertRaises(KeyError, msg="Pixel Spacing not found."):
            psf.get_pixel_spacing(path_testfiles, polarization="FF")

        self.assertEqual(psf.get_pixel_spacing(str_path), (40.0, 0.0003593261136478086))

    def test_get_proj_string(self):
        self.assertEqual(
            psf.get_proj_string(psf.get_footprint_from_manifest(path_testfiles.joinpath("manifest.safe"))),
            r"+proj=utm +zone=56J, +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        )


if __name__ == "__main__":
    unittest.main()
