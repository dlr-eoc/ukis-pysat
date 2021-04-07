#!/usr/bin/env python3

import datetime
import shutil
import uuid
from io import BytesIO
from pathlib import Path

from dateutil.parser import parse

from ukis_pysat.stacapi import StacApi

try:
    import numpy as np
    import pystac
    import requests
    import sentinelsat
    from PIL import Image
    from pystac.extensions import sat
    from shapely import geometry, wkt, ops
    from shapely.geometry import shape, mapping
except ImportError as e:
    msg = (
        "ukis_pysat.data dependencies are not installed.\n\n"
        "Please pip install as follows:\n\n"
        "  python -m pip install ukis-pysat[data] --upgrade"
    )
    raise ImportError(str(e) + "\n\n" + msg)

from ukis_pysat.file import env_get
from ukis_pysat.members import Datahub


class Source:
    """
    Provides methods to query data sources for metadata and download images and quicklooks (APIs only).
    Remote APIs and local data directories that hold metadata files are supported.
    """

    def __init__(self, datahub, catalog=None, url=None):
        """
        :param datahub: Data source (<enum 'Datahub'>).
        :param catalog: Only applicable if datahub is 'STAC_local'. Can be one of the following types:
                        Path to STAC Catalog file catalog.json (String, Path).
                        Pystac Catalog or Collection object (pystac.catalog.Catalog, pystac.collection.Collection).
                        None initializes an empty catalog.
                        (default: None)
        :param url: Only applicable if datahub is 'STAC_API'. STAC Server endpoint, reads from STAC_API_URL environment
                        variable by default
                        (default: None)
        """
        self.src = datahub

        if self.src == Datahub.STAC_local:
            # connect to STAC Catalog
            if isinstance(catalog, (pystac.catalog.Catalog, pystac.collection.Collection)):
                self.api = catalog
            elif isinstance(catalog, (str, Path)):
                href = Path(catalog).resolve().as_uri()
                self.api = pystac.catalog.Catalog.from_file(href)
            elif catalog is None:
                self.api = self._init_catalog()
            else:
                raise AttributeError(
                    f"{catalog} is not a valid STAC Catalog [catalog.json, pystac.catalog.Catalog, "
                    f"pystac.collection.Collection, None] "
                )

        elif self.src == Datahub.STAC_API:
            if url:
                self.api = StacApi(url=url)
            else:
                self.api = StacApi()

        elif self.src == Datahub.EarthExplorer:
            import landsatxplore.api

            # connect to Earthexplorer
            self.user = env_get("EARTHEXPLORER_USER")
            self.pw = env_get("EARTHEXPLORER_PW")
            self.api = landsatxplore.api.API(self.user, self.pw)

        elif self.src == Datahub.Scihub:
            # connect to Scihub
            self.user = env_get("SCIHUB_USER")
            self.pw = env_get("SCIHUB_PW")
            self.api = sentinelsat.SentinelAPI(
                self.user,
                self.pw,
                "https://scihub.copernicus.eu/apihub",
                show_progressbars=False,
            )

        else:
            raise NotImplementedError(f"{datahub} is not supported [STAC_local, STAC_API, EarthExplorer, Scihub]")

    def __enter__(self):
        return self

    def _init_catalog(self):
        """Initializes an empty STAC Catalog."""
        return pystac.catalog.Catalog(
            id=str(uuid.uuid4()),
            description=f"Creation Date: {datetime.datetime.now()}, Datahub: {self.src.value}",
            catalog_type=pystac.catalog.CatalogType.SELF_CONTAINED,
        )

    def add_items_from_directory(self, item_dir, item_glob="*.json"):
        """Adds STAC items from a directory to a STAC Catalog.

        :param item_dir: Path to directory that holds the STAC items (String).
        :param item_glob: Optional glob pattern to identify STAC items in directory (String), (default: '*.json').
        """
        if self.src == Datahub.STAC_local:
            # get all json files in item_dir that match item_substr
            item_files = sorted(Path(item_dir).rglob(item_glob))

            # load items from file and add to STAC Catalog
            for item_file in item_files:
                item = pystac.read_file(str(item_file))
                self.api.add_item(item)

        else:
            raise TypeError(f"add_items_from_directory only works for Datahub.STAC_local and not with {self.src}.")

    def query_metadata(self, platform, date, aoi, cloud_cover=None, kwargs=None):
        """Queries metadata from data source.

        :param platform: Image platform (<enum 'Platform'>).
        :param date: Date from - to in format yyyyMMdd (String or Datetime tuple).
        :param aoi: Area of interest as GeoJson file or bounding box tuple with lat lon coordinates (String, Tuple).
        :param cloud_cover: Percent cloud cover scene from - to (Integer tuple) (default: None).
        :param kwargs: Dictionary of the additional requirements for the hub used (default: None).
        :generates: Metadata item of products that match query criteria (PySTAC item).
        """
        if kwargs is None:
            kwargs = {}
        if self.src == Datahub.STAC_local:
            # query STAC Catalog for metadata
            geom = self._prep_aoi(aoi)
            for item in self.api.get_all_items():
                if item.ext.eo.cloud_cover and cloud_cover:
                    if not cloud_cover[0] <= item.ext.eo.cloud_cover < cloud_cover[1]:
                        continue
                if (
                    platform.value == item.common_metadata.platform
                    and sentinelsat.format_query_date(date[0])
                    <= sentinelsat.format_query_date(parse(item.properties["acquisitiondate"]).strftime("%Y%m%d"))
                    < sentinelsat.format_query_date(date[1])
                    and geometry.shape(item.geometry).intersects(geom)
                ):
                    yield item

        elif self.src == Datahub.STAC_API:
            raise NotImplementedError(
                f"Do this directly with our StacApi functionalities, see "
                f"https://ukis-pysat.readthedocs.io/en/latest/api/stacapi.html."
            )

        elif self.src == Datahub.EarthExplorer:
            # query EarthExplorer for metadata
            bbox = self._prep_aoi(aoi).bounds
            if cloud_cover:
                kwargs["max_cloud_cover"] = cloud_cover[1]
            products = self.api.search(
                dataset=platform.value,
                bbox=bbox,
                start_date=sentinelsat.format_query_date(date[0]),
                end_date=sentinelsat.format_query_date(date[1]),
                max_results=10000,
                **kwargs,
            )

        else:
            # query Scihub for metadata
            if cloud_cover and platform != platform.Sentinel1:
                kwargs["cloudcoverpercentage"] = cloud_cover
            products = self.api.query(
                area=self._prep_aoi(aoi).wkt,
                date=date,
                platformname=platform.value,
                **kwargs,
            )
            products = self.api.to_geojson(products)["features"]

        for meta in products:
            yield self.construct_metadata(meta=meta, platform=platform)

    def query_metadata_srcid(self, platform, srcid):
        """Queries metadata from data source by srcid.

        :param platform: Image platform (<enum 'Platform'>).
        :param srcid: Srcid of a specific product (String).
        :generates: Metadata of product that matches srcid (PySTAC item).
        """
        if self.src == Datahub.STAC_local:
            # query Spatio Temporal Asset Catalog for metadata by srcid
            for item in self.api.get_all_items():
                if item.id == srcid:
                    yield item

        elif self.src == Datahub.STAC_API:
            raise NotImplementedError(
                f"Do this directly with our StacApi functionalities, see "
                f"https://ukis-pysat.readthedocs.io/en/latest/api/stacapi.html."
            )

        elif self.src == Datahub.EarthExplorer:
            from landsatxplore.util import guess_dataset

            dataset = guess_dataset(srcid)
            metadata = self.api.metadata(self.api.get_entity_id(srcid, dataset), dataset)
            yield self.construct_metadata(meta=metadata, platform=platform)

        else:  # query Scihub for metadata by srcid
            for meta in self.api.to_geojson(self.api.query(identifier=srcid))["features"]:
                yield self.construct_metadata(meta=meta, platform=platform)

    def construct_metadata(self, meta, platform):
        """Constructs a STAC item that is harmonized across the different satellite image sources.

        :param meta: Source metadata (GeoJSON-like mapping)
        :param platform: Image platform (<enum 'Platform'>).
        :returns: PySTAC item
        """
        if self.src == Datahub.STAC_local or self.src == Datahub.STAC_API:
            raise NotImplementedError(f"construct_metadata not supported for {self.src}.")

        elif self.src == Datahub.EarthExplorer:
            item = pystac.Item(
                id=meta["display_id"],
                datetime=meta["start_time"],
                geometry=meta["spatial_coverage"].__geo_interface__,
                bbox=meta["spatial_bounds"],
                properties={
                    "producttype": "L1TP",
                    "srcuuid": meta["entity_id"],
                    "start_datetime": meta["start_time"].astimezone(tz=datetime.timezone.utc).isoformat(),
                    "end_datetime": meta["stop_time"].astimezone(tz=datetime.timezone.utc).isoformat(),
                },
                stac_extensions=[pystac.Extensions.EO, pystac.Extensions.SAT],
            )

            if "cloudCover" in meta:
                item.ext.eo.cloud_cover = round(float(meta["cloud_cover"]), 2)

            item.common_metadata.platform = platform.value

            relative_orbit = int(f"{meta['wrs_path']}{meta['wrs_row']}")
            item.ext.sat.apply(orbit_state=sat.OrbitState.DESCENDING, relative_orbit=relative_orbit)

        else:  # Scihub
            item = pystac.Item(
                id=meta["properties"]["identifier"],
                datetime=parse(meta["properties"]["beginposition"]),
                geometry=meta["geometry"],
                bbox=_get_bbox_from_geometry_string(meta["geometry"]),
                properties={
                    "producttype": meta["properties"]["producttype"],
                    "size": meta["properties"]["size"],
                    "srcurl": meta["properties"]["link"],
                    "srcuuid": meta["properties"]["uuid"],
                    "start_datetime": parse(meta["properties"]["beginposition"])
                    .astimezone(tz=datetime.timezone.utc)
                    .isoformat(),
                    "end_datetime": parse(meta["properties"]["endposition"])
                    .astimezone(tz=datetime.timezone.utc)
                    .isoformat(),
                },
                stac_extensions=[pystac.Extensions.EO, pystac.Extensions.SAT],
            )

            if "cloudcoverpercentage" in meta["properties"]:
                item.ext.eo.cloud_cover = round(float(meta["properties"]["cloudcoverpercentage"]), 2)

            item.common_metadata.platform = platform.value

            item.ext.sat.apply(
                orbit_state=sat.OrbitState[meta["properties"]["orbitdirection"].upper()],  # for enum key to work
                relative_orbit=int(meta["properties"]["orbitnumber"]),
            )

        return item

    def download_image(self, product_uuid, target_dir):
        """Downloads satellite image data to a target directory for a specific product_id.
        Incomplete downloads are continued and complete files are skipped.

        :param product_uuid: UUID of the satellite image product (String).
        :param target_dir: Target directory that holds the downloaded images (String, Path)
        """
        if isinstance(target_dir, str):
            target_dir = Path(target_dir)

        if self.src == Datahub.STAC_local or self.src == Datahub.STAC_API:
            raise NotImplementedError(
                f"download_image not supported for {self.src}. It is much easier to get the asset yourself now."
            )

        elif self.src == Datahub.EarthExplorer:
            # query EarthExplorer for srcid of product
            meta_src = self.api.request(
                "metadata",
                **{
                    "datasetName": self.src.value,
                    "entityIds": [product_uuid],
                },
            )
            product_srcid = meta_src[0]["displayId"]

            if not Path(target_dir.joinpath(product_srcid + ".zip")).is_file():
                from pylandsat import Product

                # download data from AWS if file does not already exist
                product = Product(product_srcid)
                product.download(out_dir=target_dir, progressbar=False)

                # compress download directory and remove original files
                shutil.make_archive(
                    target_dir.joinpath(product_srcid),
                    "zip",
                    root_dir=target_dir.joinpath(product_srcid),
                )
                shutil.rmtree(target_dir.joinpath(product_srcid))

        else:
            self.api.download(product_uuid, target_dir, checksum=True)

    def download_quicklook(self, product_uuid, target_dir):
        """Downloads a quicklook of the satellite image to a target directory for a specific product_id.
        It performs a very rough geocoding of the quicklooks by shifting the image to the location of the footprint.

        :param product_uuid: UUID of the satellite image product (String).
        :param target_dir: Target directory that holds the downloaded images (String, Path)
        """
        if isinstance(target_dir, str):
            target_dir = Path(target_dir)

        if self.src == Datahub.STAC_local or self.src == Datahub.STAC_API:
            raise NotImplementedError(
                f"download_quicklook not supported for {self.src}. It is much easier to get the asset yourself now, "
                f"when it is a COG you can read in an overview."
            )

        elif self.src == Datahub.EarthExplorer:
            # query EarthExplorer for url, srcid and bounds of product
            meta_src = self.api.request(
                "metadata",
                **{
                    "datasetName": self.src.value,
                    "entityIds": [product_uuid],
                },
            )
            url = meta_src[0]["browseUrl"]
            bounds = geometry.shape(meta_src[0]["spatialFootprint"]).bounds
            product_srcid = meta_src[0]["displayId"]

        else:
            # query Scihub for url, srcid and bounds of product
            meta_src = self.api.get_product_odata(product_uuid)
            url = "https://scihub.copernicus.eu/apihub/odata/v1/Products('{}')/Products('Quicklook')/$value".format(
                product_uuid
            )
            bounds = wkt.loads(meta_src["footprint"]).bounds
            product_srcid = meta_src["title"]

        # download quicklook and crop no-data borders
        response = requests.get(url, auth=(self.user, self.pw))
        quicklook = np.asarray(Image.open(BytesIO(response.content)))
        # use threshold of 50 to overcome noise in JPEG compression
        xs, ys, zs = np.where(quicklook >= 50)
        quicklook = quicklook[min(xs) : max(xs) + 1, min(ys) : max(ys) + 1, min(zs) : max(zs) + 1]
        Image.fromarray(quicklook).save(target_dir.joinpath(product_srcid + ".jpg"))

        # geocode quicklook
        quicklook_size = (quicklook.shape[1], quicklook.shape[0])
        dist_x = geometry.Point(bounds[0], bounds[1]).distance(geometry.Point(bounds[2], bounds[1])) / quicklook_size[0]
        dist_y = geometry.Point(bounds[0], bounds[1]).distance(geometry.Point(bounds[0], bounds[3])) / quicklook_size[1]
        ul_x, ul_y = bounds[0], bounds[3]
        with open(target_dir.joinpath(product_srcid + ".jpgw"), "w") as out_file:
            out_file.write(str(dist_x) + "\n")
            out_file.write(str(0.0) + "\n")
            out_file.write(str(0.0) + "\n")
            out_file.write(str(-dist_y) + "\n")
            out_file.write(str(ul_x) + "\n")
            out_file.write(str(ul_y) + "\n")

    @staticmethod
    def _prep_aoi(aoi):
        """Converts aoi to Shapely Polygon and reprojects to WGS84.

        :param aoi: Area of interest as Geojson file, WKT string or bounding box in lat lon coordinates (String,
        Tuple, __geo_interface__)
        :return: Shapely Polygon
        """
        # check if handed object is a string
        # this could include both file paths and WKT strings
        if isinstance(aoi, (str, Path)):
            # check if handed object is a file
            if Path(aoi).is_file():
                try:
                    import fiona
                    import pyproj
                except ImportError:
                    raise ImportError("if your AOI is a file optional dependencies [fiona, pyproj] are required.")
                with fiona.open(aoi, "r") as aoi:
                    # make sure crs is in epsg:4326
                    project = pyproj.Transformer.from_proj(
                        proj_from=pyproj.Proj(aoi.crs["init"]),
                        proj_to=pyproj.Proj("epsg:4326"),
                        skip_equivalent=True,
                        always_xy=True,
                    )
                    aoi = ops.transform(project.transform, geometry.shape(aoi[0]["geometry"]))
            else:
                aoi = wkt.loads(aoi)

        elif isinstance(aoi, dict):
            aoi = shape(aoi)

        elif isinstance(aoi, tuple):
            aoi = geometry.box(aoi[0], aoi[1], aoi[2], aoi[3])

        else:
            raise TypeError(f"aoi must be of type string, Path, tuple or __geo_interface__")

        return aoi

    def close(self):
        """Closes connection to or logs out of Datahub."""
        if self.src == Datahub.EarthExplorer:
            self.api.logout()
        elif self.src == Datahub.Scihub:
            self.api.session.close()
        else:
            pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def _get_bbox_from_geometry_string(geom):
    return list(geometry.shape(geom).bounds)
