import os
import unittest

from ukis_pysat.members import Datahub, Platform
from ukis_pysat.download import Source

# os.environ["EARTHEXPLORER_USER"] = "Tim"
# os.environ["EARTHEXPLORER_PW"] = "TheEnchanter"
# os.environ["SCIHUB_USER"] = "Tim"
# os.environ["SCIHUB_PW"] = "TheEnchanter"

aoi = os.path.join(os.path.dirname(__file__), "testfiles", "aoi.geojson")

queries = [
    {
        "source": Datahub.Scihub,
        "platform_name": Platform.Sentinel1,
        "date": ("20200224", "20200225"),
        "cloud_cover": None,
        "returns_srcid": "S1A_IW_SLC__1SDV_20200224T052528_20200224T052555_031390_039CF2_BEA6",
        "returns_uuid": "8a611d5b-f9d9-437e-9f55-eca18cf79fd4",
    },
    {
        "source": Datahub.Scihub,
        "platform_name": Platform.Sentinel2,
        "date": ("20200220", "20200225"),
        "cloud_cover": (0, 100),
        "returns_srcid": "S2A_MSIL2A_20200221T102041_N0214_R065_T32UQC_20200221T120618",
        "returns_uuid": "560f78fb-22b8-4904-87de-160d9236d33e",
    },
    {
        "source": Datahub.EarthExplorer,
        "platform_name": Platform.Landsat5,
        "date": ("20100201", "20100225"),
        "cloud_cover": (0, 100),
        "returns_srcid": "LT05_L1GS_193024_20100207_20161016_01_T2",
        "returns_uuid": "LT51930242010038MOR00",
    },
    {
        "source": Datahub.EarthExplorer,
        "platform_name": Platform.Landsat7,
        "date": ("20150810", "20150825"),
        "cloud_cover": (0, 50),
        "returns_srcid": "LE07_L1TP_193024_20150824_20161025_01_T1",
        "returns_uuid": "LE71930242015236ASN00",
    },
    {
        "source": Datahub.EarthExplorer,
        "platform_name": Platform.Landsat8,
        "date": ("20200310", "20200325"),
        "cloud_cover": (0, 20),
        "returns_srcid": "LC08_L1TP_193024_20200322_20200326_01_T1",
        "returns_uuid": "LC81930242020082LGN00",
    },
]


class DownloadTest(unittest.TestCase):
    # @unittest.skip("uncomment when you set ENVs with credentials")
    def test_query_metadata(self):
        for i in range(len(queries)):
            with Source(source=queries[i]["source"]) as src:
                meta = src.query_metadata(
                    aoi=aoi,
                    platform=queries[i]["platform_name"],
                    date=queries[i]["date"],
                    cloud_cover=queries[i]["cloud_cover"],
                )
            returns_srcid = meta["properties"]["srcid"]
            returns_uuid = meta["properties"]["srcuuid"]
            self.assertEqual(returns_srcid, (queries[i]["returns_srcid"]))
            self.assertEqual(returns_uuid, (queries[i]["returns_uuid"]))

    def test_get_metadata(self):
        source_dir = os.path.join(os.path.dirname(__file__), "testfiles")
        src = Source(source=Datahub.file, source_dir=source_dir)
        meta = src.get_metadata(product_id="S2A_MSIL2A_20200221T102041_N0214_R065_T32UQC_20200221T120618")
        returns_srcid = meta["properties"]["srcid"]
        returns_uuid = meta["properties"]["srcuuid"]
        self.assertEqual(
            returns_srcid, "S2A_MSIL2A_20200221T102041_N0214_R065_T32UQC_20200221T120618",
        )
        self.assertEqual(returns_uuid, "560f78fb-22b8-4904-87de-160d9236d33e")

    @unittest.skip("uncomment when you set ENVs with credentials")
    def test_download_image(self):
        # TODO
        pass

    @unittest.skip("uncomment when you set ENVs with credentials")
    def test_download_quicklook(self):
        target_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfiles")
        for i in range(len(queries)):
            with Source(source=queries[i]["source"]) as src:
                src.download_quicklook(
                    platform=queries[i]["platform_name"],
                    product_uuid=queries[i]["returns_uuid"],
                    product_srcid=queries[i]["returns_srcid"],
                    target_dir=target_dir,
                )
            self.assertTrue(os.path.isfile(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpg"))
            self.assertTrue(os.path.isfile(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpgw"))
            os.remove(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpg")
            os.remove(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpgw")


if __name__ == "__main__":
    unittest.main()
