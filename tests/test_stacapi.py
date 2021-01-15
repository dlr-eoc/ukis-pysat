import unittest

import geojson
from shapely import wkt

from ukis_pysat.stacapi import StacApi


class StacApiTest(unittest.TestCase):
    def setUp(self):
        self.url = "https://earth-search.aws.element84.com/v0/"
        self.api = StacApi(url=self.url)

        self.aoi = geojson.Feature(
            geometry=wkt.loads(
                r"POLYGON((11.00 48.00, 11.05 48.00,11.05 48.05, 11.00 48.05, 11.00 48.00))"),
            properties={},
        ).geometry

    def test_init(self):
        self.assertEqual(self.api.url, self.url)

    def test_collections(self):
        collections = self.api.get_collections()
        self.assertEqual(len(collections), 4)

    def test_get_collections(self):
        collection = self.api.get_collections(collection_id=r"sentinel-s2-l2a")
        self.assertEqual(collection[0].id, r"sentinel-s2-l2a")

    def test_count(self):
        cnt = self.api.count(collection=r"sentinel-s2-l2a", datetime=r"2019-01-01T00:00:00Z/2019-01-01T23:59:59Z")
        self.assertEqual(cnt, 25030)

    @unittest.skip  # TODO does not work because endpoints expects quotes around ID
    def test_get_item(self):
        item = self.api.get_items(collection="sentinel-s2-l2a", ids=["S2A_35VLG_20210114_0_L2A"], limit=1)
        self.assertEqual(item.id, "S2A_35VLG_20210114_0_L2A")

    def test_get_item_intersects(self):
        cnt = self.api.count(collection="sentinel-s2-l2a", intersects=self.aoi)
        self.assertEqual(1580, cnt)

    def test_get_items_limit(self, limit=31):
        items = self.api.get_items(collection="sentinel-s2-l2a", intersects=self.aoi, limit=limit)
        self.assertEqual(limit, len(items))


if __name__ == '__main__':
    unittest.main()
