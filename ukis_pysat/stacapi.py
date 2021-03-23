import os
from urllib.parse import urljoin

try:
    import requests
    from pystac import Item, Collection
except ImportError as e:
    msg = (
        "ukis_pysat.data dependencies are not installed.\n\n"
        "Please pip install as follows:\n\n"
        "  python -m pip install ukis-pysat[data] --upgrade"
    )
    raise ImportError(str(e) + "\n\n" + msg)


from ukis_pysat.stacapi_io import STACAPI_IO


class StacApiError(Exception):
    pass


class StacApi:
    # TODO be aware of https://github.com/azavea/franklin/issues/471
    def __init__(self, url=os.getenv("STAC_API_URL", None)):
        """API to query STAC as part of ukis-pysat.data
        :param url: STAC Server endpoint, reads from STAC_API_URL environment variable by default
        """
        if url is None:
            raise StacApiError("URL not provided, pass into StacApi or define STAC_API_URL environment variable")
        self.url = url.rstrip("/") + "/"

    def _handle_query(self, url=None, headers=None, **kwargs):
        url = url or urljoin(self.url, "search")
        response = self._query(url, kwargs=kwargs, headers=headers)
        if response.status_code != 200:
            raise StacApiError(response.text)
        return response.json()

    @staticmethod
    def _query(url, kwargs, headers):
        if {"intersects", "bbox"}.intersection(kwargs):
            # TODO intersects will be deprecated with v1.0.0-beta.2 and replaced with OGC CQL
            return requests.post(url, json=kwargs, headers=headers)
        else:
            return requests.get(url, kwargs, headers=headers)

    def count(self, headers=None, **kwargs):
        """lightweight query to get count of results to expect
        :param headers: headers (optional)
        :param kwargs: search parameters (optional)
        :returns number of found results"""
        res = self._handle_query(headers=headers, **kwargs)
        return res["context"]["matched"]

    def get_items(self, limit=100, headers=None, **kwargs):
        """get items or single item
        :param limit: max number of items returned (default 100)
        :param headers: headers (optional)
        :param kwargs: search parameters (optional) See: https://github.com/radiantearth/stac-api-spec/tree/master/item-search#query-parameter-table
        :returns list with pystac.items"""
        next_page = urljoin(self.url, "search")
        limit = kwargs.get("limit", limit)
        items = []

        while next_page:
            res = self._handle_query(url=next_page, headers=headers, **kwargs)

            if not res["links"]:
                next_page = None
            else:
                next_page = res["links"][0]["href"] if res["links"][0]["rel"] == "next" else None

            for f in res["features"]:
                if len(items) == limit:
                    next_page = None
                    break
                """Instead of reading Items from_dict we rebuild the URLs so that they fit to the file system in use"""
                items.append(STACAPI_IO.build_url(f))

        return items

    def get_collections(self, collection_id=None, headers=None, **kwargs):
        """get all collections or get collection by ID
        :param collection_id: ID of collection (optional)
        :param headers: headers (optional)
        :param kwargs: search parameters (optional)
        :returns list with pystac.collections"""
        url = urljoin(self.url, f"collections/{collection_id}" if collection_id else "collections")
        res = self._handle_query(url=url, headers=headers, **kwargs)
        if isinstance(res, dict):
            res = res.get("collections", [res])
        return [Collection.from_dict(c) for c in res]
