import os
import traceback
import unittest

from ukis_pysat.members import Datahub, Platform
from ukis_pysat.data import Source

# os.environ["EARTHEXPLORER_USER"] = "Tim"
# os.environ["EARTHEXPLORER_PW"] = "TheEnchanter"
# os.environ["SCIHUB_USER"] = "Tim"
# os.environ["SCIHUB_PW"] = "TheEnchanter"

aoi_4326 = os.path.join(os.path.dirname(__file__), "testfiles", "aoi_4326.geojson")
aoi_3857 = os.path.join(os.path.dirname(__file__), "testfiles", "aoi_3857.geojson")
aoi_bbox = (11.90, 51.46, 11.94, 51.50)
target_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testfiles")

queries = [
    {
        "source": Datahub.Scihub,
        "platform_name": Platform.Sentinel1,
        "date": ("20200224", "20200225"),
        "aoi": aoi_4326,
        "cloud_cover": None,
        "returns_srcid": "S1A_IW_SLC__1SDV_20200224T052528_20200224T052555_031390_039CF2_BEA6",
        "returns_uuid": "8a611d5b-f9d9-437e-9f55-eca18cf79fd4",
    },
    {
        "source": Datahub.Scihub,
        "platform_name": Platform.Sentinel2,
        "date": ("20200220", "20200225"),
        "aoi": aoi_3857,
        "cloud_cover": (0, 100),
        "returns_srcid": "S2A_MSIL2A_20200221T102041_N0214_R065_T32UQC_20200221T120618",
        "returns_uuid": "560f78fb-22b8-4904-87de-160d9236d33e",
    },
    {
        "source": Datahub.Scihub,
        "platform_name": Platform.Sentinel3,
        "date": ("20200220", "20200225"),
        "aoi": aoi_bbox,
        "cloud_cover": (0, 100),
        "returns_srcid": "S3B_OL_2_LRR____20200220T092808_20200220T101154_20200221T143235_2626_035_364______LN1_O_NT_002",
        "returns_uuid": "a50c1e2f-0688-4be1-ae2f-dc69fe8b170a",
    },
    {
        "source": Datahub.EarthExplorer,
        "platform_name": Platform.Landsat5,
        "date": ("20100201", "20100225"),
        "aoi": aoi_4326,
        "cloud_cover": (0, 100),
        "returns_srcid": "LT05_L1GS_193024_20100207_20161016_01_T2",
        "returns_uuid": "LT51930242010038MOR00",
    },
    {
        "source": Datahub.EarthExplorer,
        "platform_name": Platform.Landsat7,
        "date": ("20150810", "20150825"),
        "aoi": aoi_3857,
        "cloud_cover": (0, 50),
        "returns_srcid": "LE07_L1TP_193024_20150824_20161025_01_T1",
        "returns_uuid": "LE71930242015236ASN00",
    },
    {
        "source": Datahub.EarthExplorer,
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
            AttributeError, msg=f"{traceback.format_exc()} source_dir has to be set if source is Datahub.file."
        ):
            Source(Datahub.file)

        src = Source(Datahub.file, source_dir=target_dir)
        self.assertEqual(src.api, target_dir)

        with self.assertRaises(NotImplementedError, msg=f"Hub is not supported [file, EarthExplorer, Scihub]."):
            Source("Hub")

        with self.assertRaises(AttributeError):
            Source(Datahub.Hub)

    def test_exceptions(self):
        src = Source(Datahub.file, source_dir=target_dir)
        with self.assertRaises(TypeError, msg=f"aoi must be of type string or tuple"):
            src.prep_aoi(1)

        with self.assertRaises(NotImplementedError, msg="File metadata query not yet supported."):
            src.query_metadata(platform=Datahub.file, date="20200101", aoi=aoi_4326,)

        with self.assertRaises(NotImplementedError, msg="File metadata construction  not yet supported."):
            src.construct_metadata("")

    # @unittest.skip("uncomment when you set ENVs with credentials")
    def test_query_metadata(self):
        for i in range(len(queries)):
            with Source(source=queries[i]["source"]) as src:
                # query metadata
                meta = src.query_metadata(
                    platform=queries[i]["platform_name"],
                    date=queries[i]["date"],
                    aoi=queries[i]["aoi"],
                    cloud_cover=queries[i]["cloud_cover"],
                )
                # filter metadata by srcid
                meta.filter(filter_dict={"srcid": queries[i]["returns_srcid"]},)
                # save filtered metadata
                meta.save(target_dir)
            returns_srcid = meta.to_geojson()[0]["properties"]["srcid"]
            returns_uuid = meta.to_geojson()[0]["properties"]["srcuuid"]
            self.assertEqual(returns_srcid, (queries[i]["returns_srcid"]))
            self.assertEqual(returns_uuid, (queries[i]["returns_uuid"]))
            self.assertTrue(os.path.isfile(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".json"))
            os.remove(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".json")

    # @unittest.skip("uncomment when you set ENVs with credentials")
    def test_download_image(self):
        src = Source(Datahub.file, source_dir=target_dir)
        with self.assertRaises(Exception, msg="download_image() not supported for Datahub.file."):
            src.download_image(platform=Datahub.file, product_uuid="1", target_dir=target_dir,)
        # TODO download tests

    # @unittest.skip("uncomment when you set ENVs with credentials")
    def test_download_quicklook(self):
        for i in range(len(queries)):
            with Source(source=queries[i]["source"]) as src:
                # download geocoded quicklook
                src.download_quicklook(
                    platform=queries[i]["platform_name"],
                    product_uuid=queries[i]["returns_uuid"],
                    target_dir=target_dir,
                )
            self.assertTrue(os.path.isfile(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpg"))
            self.assertTrue(os.path.isfile(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpgw"))
            os.remove(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpg")
            os.remove(os.path.join(target_dir, queries[i]["returns_srcid"]) + ".jpgw")

        src = Source(Datahub.file, source_dir=target_dir)
        with self.assertRaises(NotImplementedError, msg=f"download_quicklook not supported for Datahub.file."):
            src.download_quicklook(platform=Datahub.file, product_uuid="1", target_dir=target_dir,)


if __name__ == "__main__":
    unittest.main()
