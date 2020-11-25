#!/usr/bin/env python3

import datetime
import shutil
import uuid
from io import BytesIO
from pathlib import Path

from dateutil.parser import parse

try:
    import fiona
    import landsatxplore.api
    import numpy as np
    import pyproj
    import pystac
    import requests
    import sentinelsat
    from PIL import Image
    from pylandsat import Product
    from pystac.extensions import sat  # TODO https://github.com/stac-utils/pystac/issues/133
    from shapely import geometry, wkt, ops
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

    catalog = None

    def __init__(self, datahub, catalog=None):
        """
        :param datahub: Data source (<enum 'Datahub'>).
        :param catalog: Path to catalog.json that holds the metadata if datahub is 'STAC' (String, Path).
        """
        self.src = datahub

        if self.src == Datahub.STAC:


            # TODO: catalog should be able to take catalog.json or catalog object,
            # if None a new empty catalog will be created
            # TODO: self.api is where the main catalog (the one to query from) is stored
            if not isinstance(catalog, (str, Path)):
                raise AttributeError(f"'catalog' has to be set if datahub is 'STAC'.")
            else:
                self.api = None
                self.init_catalog(catalog=catalog)



        elif self.src == Datahub.EarthExplorer:
            # connect to Earthexplorer
            self.user = env_get("EARTHEXPLORER_USER")
            self.pw = env_get("EARTHEXPLORER_PW")
            self.api = landsatxplore.api.API(self.user, self.pw)

        elif self.src == Datahub.Scihub:
            # connect to Scihub
            self.user = env_get("SCIHUB_USER")
            self.pw = env_get("SCIHUB_PW")
            self.api = sentinelsat.SentinelAPI(
                self.user, self.pw, "https://scihub.copernicus.eu/dhus", show_progressbars=False,
            )

        else:
            raise NotImplementedError(f"{datahub} is not supported [STAC, EarthExplorer, Scihub]")

    def __enter__(self):
        return self

    def init_catalog(self, catalog=None):
        """ Initializes PySTAC Catalog

        :param catalog: PySTAC Catalog or Collection if already exists
        """
        if isinstance(catalog, (pystac.catalog.Catalog, pystac.collection.Collection)):
            self.catalog = catalog
        elif isinstance(catalog, (str, Path)):
            href = Path(catalog).resolve().as_uri()
            self.catalog = pystac.catalog.Catalog.from_file(href)
        else:
            self.catalog = pystac.catalog.Catalog(
                id=str(uuid.uuid4()),
                description=f"Creation Date: {datetime.datetime.now()}, Datahub: {self.src.value}",
                catalog_type=pystac.catalog.CatalogType.SELF_CONTAINED,
            )

    def query_metadata(self, platform, date, aoi, cloud_cover=None):
        """Queries satellite image metadata from data source.

        :param platform: Image platform (<enum 'Platform'>).
        :param date: Date from - to (String or Datetime tuple). Expects a tuple of (start, end), e.g.
            (yyyyMMdd, yyyy-MM-ddThh:mm:ssZ, NOW, NOW-<n>DAY(S), HOUR(S), MONTH(S), etc.)
        :param aoi: Area of interest as GeoJson file or bounding box tuple with lat lon coordinates (String, Tuple).
        :param cloud_cover: Percent cloud cover scene from - to (Integer tuple).
        :returns: Metadata catalog of products that match query criteria (PySTAC Catalog).
        """
        if self.src == Datahub.STAC:
            for item in self.catalog.get_all_items():
                if item.ext.eo.cloud_cover and cloud_cover:  # not always relevant, but if no need to check rest
                    if not cloud_cover[0] <= item.ext.eo.cloud_cover < cloud_cover[1]:
                        self.catalog.remove_item(item.id)
                        continue
                if not (
                    platform.value == item.common_metadata.platform
                    and parse(sentinelsat.format_query_date(date[0]))
                    <= parse(item.properties["acquisitiondate"])  # TODO preferably item.datetime again
                    < parse(sentinelsat.format_query_date(date[1]))
                    and geometry.shape(item.geometry).intersects(self.prep_aoi(aoi))
                ):
                    self.catalog.remove_item(item.id)
            return self.catalog

        elif self.src == Datahub.EarthExplorer:
            # query Earthexplorer for metadata
            bbox = self.prep_aoi(aoi).bounds
            kwargs = {}
            if cloud_cover:
                kwargs["max_cloud_cover"] = cloud_cover[1]
            meta_src = self.api.search(
                dataset=platform.value,
                bbox=[bbox[1], bbox[0], bbox[3], bbox[2]],
                start_date=sentinelsat.format_query_date(date[0]),
                end_date=sentinelsat.format_query_date(date[1]),
                max_results=10000,
                **kwargs,
            )

        else:
            # query Scihub for metadata
            kwargs = {}
            if cloud_cover and platform != platform.Sentinel1:
                kwargs["cloudcoverpercentage"] = cloud_cover
            meta_src = self.api.query(area=self.prep_aoi(aoi).wkt, date=date, platformname=platform.value, **kwargs,)
            meta_src = self.api.to_geojson(meta_src)["features"]

        if not self.catalog:
            self.init_catalog()

        for item in meta_src:
            self.catalog.add_item(self.construct_metadata(meta_src=item, platform=platform))
        return self.catalog

    def query_metadata_srcid(self, platform, srcid):
        """Queries satellite image metadata from data source by srcid.

        :param platform: Image platform (<enum 'Platform'>).
        :param srcid: Srcid of a specific product which is essentially its name (String).
        :returns: Metadata of product that matches srcid (MetadataCollection object).
        """
        if self.src == Datahub.STAC:
            for item in self.catalog.get_all_items():  # filter relevant item
                if item.id != srcid:
                    self.catalog.remove_item(item.id)
            return self.catalog

        elif self.src == Datahub.EarthExplorer:
            # query Earthexplorer for metadata by srcid and construct MetadataCollection
            # TODO could not figure out how to directly query detailed metadata by srcid, therefore here we
            # query first for scene acquisitiondate and footprint and use these to query detailed metadata.
            meta_src = self.api.request(
                "metadata",
                **{"datasetName": platform.value, "entityIds": self.api.lookup(platform.value, srcid, inverse=True)},
            )
            date_from = meta_src[0]["acquisitionDate"].replace("-", "")
            date_to = (datetime.datetime.strptime(date_from, "%Y%m%d") + datetime.timedelta(days=1)).strftime("%Y%m%d")
            aoi = geometry.shape(meta_src[0]["spatialFootprint"]).bounds
            self.query_metadata(platform=platform, date=(date_from, date_to), aoi=aoi)
            for item in self.catalog.get_all_items():  # filter relevant item
                if item.id != srcid:
                    self.catalog.remove_item(item.id)
            return self.catalog

        else:  # query Scihub for metadata by srcid and construct MetadataCollection
            meta_src = self.api.to_geojson(self.api.query(identifier=srcid))["features"]

            if not self.catalog:
                self.init_catalog()

            for item in meta_src:
                self.catalog.add_item(self.construct_metadata(meta_src=item, platform=platform))
            return self.catalog

    def construct_metadata(self, meta_src, platform):
        """Constructs a STAC item that is harmonized across the different satellite image sources.

        :param meta_src: Source metadata (GeoJSON-like mapping)
        :param platform: Image platform (<enum 'Platform'>).
        :returns: PySTAC item
        """
        if self.src == Datahub.STAC:
            raise NotImplementedError(f"construct_metadata not supported for {self.src}.")

        elif self.src == Datahub.EarthExplorer:
            item = pystac.Item(
                id=meta_src["displayId"],
                datetime=datetime.datetime.now(),
                geometry=meta_src["spatialFootprint"],
                bbox=_get_bbox_from_geometry_string(meta_src["spatialFootprint"]),
                properties={
                    "producttype": "L1TP",
                    "srcurl": meta_src["dataAccessUrl"],
                    "srcuuid": meta_src["entityId"],
                    "acquisitiondate": meta_src["acquisitionDate"],
                    "ingestiondate": meta_src["modifiedDate"],
                },
                stac_extensions=[pystac.Extensions.EO, pystac.Extensions.SAT],
            )

            if "cloudCover" in meta_src:
                item.ext.eo.cloud_cover = round(float(meta_src["cloudCover"]), 2)

            item.common_metadata.platform = platform.value

            relative_orbit = int(
                meta_src["summary"][
                    meta_src["summary"].find("Path: ") + len("Path: ") : meta_src["summary"].rfind(", Row: ")
                ]
            )
            item.ext.sat.apply(orbit_state=sat.OrbitState.DESCENDING, relative_orbit=relative_orbit)

        else:  # Scihub
            item = pystac.Item(
                id=meta_src["properties"]["identifier"],
                datetime=datetime.datetime.now(),
                geometry=meta_src["geometry"],
                bbox=_get_bbox_from_geometry_string(meta_src["geometry"]),
                properties={
                    "producttype": meta_src["properties"]["producttype"],
                    "size": meta_src["properties"]["size"],
                    "srcurl": meta_src["properties"]["link"],
                    "srcuuid": meta_src["properties"]["uuid"],
                    "acquisitiondate": meta_src["properties"]["beginposition"],
                    "ingestiondate": meta_src["properties"]["ingestiondate"],
                },
                stac_extensions=[pystac.Extensions.EO, pystac.Extensions.SAT],
            )

            if "cloudcoverpercentage" in meta_src["properties"]:
                item.ext.eo.cloud_cover = round(float(meta_src["properties"]["cloudcoverpercentage"]), 2)

            item.common_metadata.platform = platform.value

            item.ext.sat.apply(
                orbit_state=sat.OrbitState[meta_src["properties"]["orbitdirection"].upper()],  # for enum key to work
                relative_orbit=int(meta_src["properties"]["orbitnumber"]),
            )

        return item

    def download_image(self, platform, product_uuid, target_dir):
        """Downloads satellite image data to a target directory for a specific product_id.
        Incomplete downloads are continued and complete files are skipped.

        :param platform: Image platform (<enum 'Platform'>).
        :param product_uuid: UUID of the satellite image product (String).
        :param target_dir: Target directory that holds the downloaded images (String, Path)
        """
        if isinstance(target_dir, str):
            target_dir = Path(target_dir)
        if self.src == Datahub.STAC:
            raise NotImplementedError(f"download_image not supported for {self.src}.")

        elif self.src == Datahub.EarthExplorer:
            # query EarthExplorer for srcid of product
            meta_src = self.api.request("metadata", **{"datasetName": platform.value, "entityIds": [product_uuid],},)
            product_srcid = meta_src[0]["displayId"]

            if not Path(target_dir.joinpath(product_srcid + ".zip")).is_file():
                # download data from AWS if file does not already exist
                product = Product(product_srcid)
                product.download(out_dir=target_dir, progressbar=False)

                # compress download directory and remove original files
                shutil.make_archive(
                    target_dir.joinpath(product_srcid), "zip", root_dir=target_dir.joinpath(product_srcid),
                )
                shutil.rmtree(target_dir.joinpath(product_srcid))

        else:
            self.api.download(product_uuid, target_dir, checksum=True)

    def download_quicklook(self, platform, product_uuid, target_dir):
        """Downloads a quicklook of the satellite image to a target directory for a specific product_id.
        It performs a very rough geocoding of the quicklooks by shifting the image to the location of the footprint.

        :param platform: Image platform (<enum 'Platform'>).
        :param product_uuid: UUID of the satellite image product (String).
        :param target_dir: Target directory that holds the downloaded images (String, Path)
        """
        if isinstance(target_dir, str):
            target_dir = Path(target_dir)
        if self.src == Datahub.STAC:
            raise NotImplementedError(f"download_quicklook not supported for {self.src}.")

        elif self.src == Datahub.EarthExplorer:
            # query EarthExplorer for url, srcid and bounds of product
            meta_src = self.api.request("metadata", **{"datasetName": platform.value, "entityIds": [product_uuid],},)
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
    def prep_aoi(aoi):
        """Converts aoi to Shapely Polygon and reprojects to WGS84.

        :param aoi: Area of interest as Geojson file, WKT string or bounding box in lat lon coordinates (String, Tuple)
        :return: Shapely Polygon
        """
        # check if handed object is a string
        # this could include both file paths and WKT strings
        if isinstance(aoi, (str, Path)):
            # check if handed object is a file
            if Path(aoi).is_file():
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

        elif isinstance(aoi, tuple):
            aoi = geometry.box(aoi[0], aoi[1], aoi[2], aoi[3])

        else:
            raise TypeError(f"aoi must be of type string, Path or tuple")

        return aoi

    def close(self):
        """Closes connection to or logs out of Datahub"""
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
