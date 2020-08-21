import traceback
import unittest
from pathlib import Path

from ukis_pysat.data import Source
from ukis_pysat.members import Datahub, Platform

# os.environ["EARTHEXPLORER_USER"] = "Tim"
# os.environ["EARTHEXPLORER_PW"] = "TheEnchanter"
# os.environ["SCIHUB_USER"] = "Tim"
# os.environ["SCIHUB_PW"] = "TheEnchanter"

target_dir = Path(__file__).parents[0] / "testfiles"
aoi_4326 = target_dir / "aoi_4326.geojson"
aoi_3857 = target_dir / "aoi_3857.geojson"
aoi_wkt = "POLYGON((11.09 47.94, 11.06 48.01, 11.12 48.11, 11.18 48.11, 11.18 47.94, 11.09 47.94))"
aoi_bbox = (11.90, 51.46, 11.94, 51.50)


queries = [
    {
        "datahub": Datahub.File,
        "datadir": target_dir,
        "platform_name": Platform.Sentinel2,
        "date": ("20200403", "20200409"),
        "aoi": aoi_bbox,
        "cloud_cover": (0, 5),
        "returns_srcid": "S2B_MSIL1C_20200406T101559_N0209_R065_T32UPC_20200406T130159",
        "returns_uuid": "d7f7f33c-acd0-4a50-829c-7ca54aee1c50",
    },
    {
        "datahub": Datahub.Scihub,
        "datadir": None,
        "platform_name": Platform.Sentinel1,
        "date": ("20200224", "20200225"),
        "aoi": aoi_4326,
        "cloud_cover": None,
        "returns_srcid": "S1A_IW_SLC__1SDV_20200224T052528_20200224T052555_031390_039CF2_BEA6",
        "returns_uuid": "8a611d5b-f9d9-437e-9f55-eca18cf79fd4",
    },
    {
        "datahub": Datahub.Scihub,
        "datadir": None,
        "platform_name": Platform.Sentinel1,
        "date": ("20200502", "20200503"),
        "aoi": aoi_wkt,
        "cloud_cover": None,
        "returns_srcid": "S1A_IW_GRDH_1SDV_20200502T170726_20200502T170751_032389_03BFFF_3105",
        "returns_uuid": "a28e1042-f221-4716-8298-01bca35e6187",
    },
    {
        "datahub": Datahub.Scihub,
        "datadir": None,
        "platform_name": Platform.Sentinel2,
        "date": ("20200220", "20200225"),
        "aoi": aoi_3857,
        "cloud_cover": (0, 100),
        "returns_srcid": "S2A_MSIL2A_20200221T102041_N0214_R065_T32UQC_20200221T120618",
        "returns_uuid": "560f78fb-22b8-4904-87de-160d9236d33e",
    },
    {
        "datahub": Datahub.Scihub,
        "datadir": None,
        "platform_name": Platform.Sentinel3,
        "date": ("20200220", "20200225"),
        "aoi": aoi_bbox,
        "cloud_cover": (0, 100),
        "returns_srcid": "S3B_OL_2_LRR____20200220T092808_20200220T101154_20200221T143235_2626_035_364______LN1_O_NT_002",
        "returns_uuid": "a50c1e2f-0688-4be1-ae2f-dc69fe8b170a",
    },
    {
        "datahub": Datahub.EarthExplorer,
        "datadir": None,
        "platform_name": Platform.Landsat5,
        "date": ("20100201", "20100225"),
        "aoi": aoi_4326,
        "cloud_cover": (0, 100),
        "returns_srcid": "LT05_L1GS_193024_20100207_20161016_01_T2",
        "returns_uuid": "LT51930242010038MOR00",
    },
    {
        "datahub": Datahub.EarthExplorer,
        "datadir": None,
        "platform_name": Platform.Landsat7,
        "date": ("20150810", "20150825"),
        "aoi": aoi_3857,
        "cloud_cover": (0, 50),
        "returns_srcid": "LE07_L1TP_193024_20150824_20161025_01_T1",
        "returns_uuid": "LE71930242015236ASN00",
    },
    {
        "datahub": Datahub.EarthExplorer,
        "datadir": None,
        "platform_name": Platform.Landsat8,
        "date": ("20200310", "20200325"),
        "aoi": aoi_bbox,
        "cloud_cover": (0, 20),
        "returns_srcid": "LC08_L1TP_193024_20200322_20200326_01_T1",
        "returns_uuid": "LC81930242020082LGN00",
    },
]


class DownloadTest(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(
            AttributeError, msg=f"{traceback.format_exc()} datadir has to be set if datahub is File."
        ):
            Source(datahub=Datahub.File)

        src = Source(datahub=Datahub.File, datadir=target_dir)
        self.assertEqual(src.api, target_dir)

        with self.assertRaises(NotImplementedError, msg=f"Hub is not supported [File, EarthExplorer, Scihub]."):
            Source(datahub="Hub")

        with self.assertRaises(AttributeError):
            Source(datahub=Datahub.Hub)

    def test_exceptions(self):
        src = Source(datahub=Datahub.File, datadir=target_dir)
        with self.assertRaises(TypeError, msg=f"aoi must be of type string or tuple"):
            src.prep_aoi(1)

    # @unittest.skip("until API is reachable again")
    # @unittest.skip("uncomment when you set ENVs with credentials")
    def test_query_metadata(self):
        for i in range(len(queries)):
            with Source(datahub=queries[i]["datahub"], datadir=queries[i]["datadir"]) as src:
                meta = src.query_metadata(
                    platform=queries[i]["platform_name"],
                    date=queries[i]["date"],
                    aoi=queries[i]["aoi"],
                    cloud_cover=queries[i]["cloud_cover"],
                )
                meta.filter(filter_dict={"srcid": queries[i]["returns_srcid"]},)
                meta.save(target_dir)
            returns_srcid = meta.to_geojson()[0]["properties"]["srcid"]
            returns_uuid = meta.to_geojson()[0]["properties"]["srcuuid"]
            self.assertEqual(returns_srcid, (queries[i]["returns_srcid"]))
            self.assertEqual(returns_uuid, (queries[i]["returns_uuid"]))
            self.assertTrue(target_dir.joinpath(queries[i]["returns_srcid"] + ".json").is_file())
            target_dir.joinpath(queries[i]["returns_srcid"] + ".json").unlink()

    # @unittest.skip("uncomment when you set ENVs with credentials")
    def test_download_image(self):
        src = Source(datahub=Datahub.File, datadir=target_dir)
        with self.assertRaises(Exception, msg="download_image not supported for Datahub.File."):
            src.download_image(
                platform=Datahub.File, product_uuid="1", target_dir=target_dir,
            )
        # TODO download tests

    # @unittest.skip("until API is reachable again")
    # @unittest.skip("uncomment when you set ENVs with credentials")
    def test_download_quicklook(self):
        for i in range(len(queries)):
            with Source(datahub=queries[i]["datahub"], datadir=queries[i]["datadir"]) as src:
                if queries[i]["datahub"] == Datahub.File:
                    with self.assertRaises(Exception, msg="download_quicklook not supported for Datahub.File."):
                        src.download_quicklook(
                            platform=queries[i]["platform_name"],
                            product_uuid=queries[i]["returns_uuid"],
                            target_dir=target_dir,
                        )
                else:
                    src.download_quicklook(
                        platform=queries[i]["platform_name"],
                        product_uuid=queries[i]["returns_uuid"],
                        target_dir=target_dir,
                    )
                    self.assertTrue(target_dir.joinpath(queries[i]["returns_srcid"] + ".jpg").is_file())
                    self.assertTrue(target_dir.joinpath(queries[i]["returns_srcid"] + ".jpgw").is_file())
                    target_dir.joinpath(queries[i]["returns_srcid"] + ".jpg").unlink()
                    target_dir.joinpath(queries[i]["returns_srcid"] + ".jpgw").unlink()

        src = Source(datahub=Datahub.File, datadir=target_dir)
        with self.assertRaises(NotImplementedError, msg=f"download_quicklook not supported for Datahub.File."):
            src.download_quicklook(
                platform=Datahub.File, product_uuid="1", target_dir=target_dir,
            )


if __name__ == "__main__":
    unittest.main()
