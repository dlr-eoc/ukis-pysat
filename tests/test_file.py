import os
import unittest
import ukis_pysat.file as psf

path_testfiles = os.path.join(os.path.dirname(__file__), "testfiles")


class FileTest(unittest.TestCase):
    def test_get_sentinel_scene_from_dir(self):
        with psf.get_sentinel_scene_from_dir(path_testfiles) as (full_path, ident):
            self.assertEqual("S1M_hello_from_inside", ident)

        with psf.get_sentinel_scene_from_dir(
            os.path.join(path_testfiles, "another_scene")
        ) as (full_path, ident):
            self.assertEqual("S2__IN_FOLDER", ident)

    def test_get_polarization_from_s1_filename(self):
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_1SDH_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            "HH",
        )
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_1SSH_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            "HH",
        )
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_2SSV_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            "VV",
        )
        self.assertEqual(
            psf.get_polarization_from_s1_filename(
                "MMM_BB_TTTR_1SDV_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip",
                True,
            ),
            ["VV", "VH"],
        )

    def test_get_ts_from_sentinel_filename(self):
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S3M_OL_L_TTTTTT_yyyymmddThhmmss_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_i_GGG_c.SEN3"
            ),
            "yyyymmddThhmmss",
        )
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "MMM_BB_TTTR_LFPP_YYYYMMDDTHHMMSS_20200113T002219_OOOOOO_DDDDDD_CCCC.SAFE.zip",
                False,
            ),
            "20200113T002219",
        )
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S1M_BB_TTTR_LFPP_20200113T074619_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip"
            ),
            "20200113T074619",
        )
        self.assertEqual(
            psf.get_ts_from_sentinel_filename(
                "S2AM_MSIXXX_YYYYMMDDHHMMSS_Nxxyy_ROOO_Txxxxx_<Product Discriminator>.SAFE"
            ),
            "YYYYMMDDHHMMSS",
        )

    def test_get_footprint_from_manifest(self):
        self.assertEqual(
            psf.get_footprint_from_manifest(
                os.path.join(path_testfiles, "manifest.safe")
            ).wkt,
            "POLYGON ((149.766922 -24.439564, 153.728622 -23.51771, 154.075058 -24.737713, 150.077042 "
            "-25.668921, 149.766922 -24.439564))",
        )

    def test_get_origin_from_manifest(self):
        self.assertEqual(
            psf.get_origin_from_manifest(os.path.join(path_testfiles, "manifest.safe")),
            "United Kingdom",
        )

    def test_get_ipf_from_manifest(self):
        self.assertEqual(
            psf.get_ipf_from_manifest(os.path.join(path_testfiles, "manifest.safe")),
            2.82,
        )

    def test_get_pixel_spacing(self):
        self.assertEqual(
            psf.get_pixel_spacing(path_testfiles), (40.0, 0.0003593261136478086)
        )

    def test_get_proj_string(self):
        self.assertEqual(
            psf.get_proj_string(
                psf.get_footprint_from_manifest(
                    os.path.join(path_testfiles, "manifest.safe")
                )
            ),
            r"+proj=utm +zone=56J, +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        )


if __name__ == "__main__":
    unittest.main()
