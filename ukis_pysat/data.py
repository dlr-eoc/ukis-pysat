#!/usr/bin/env python3

import datetime
import json
import logging
import os
import shutil
from io import BytesIO
from typing import List

try:
    import fiona
    import landsatxplore.api
    import numpy as np
    import pyproj
    import requests
    import sentinelsat
    from PIL import Image
    from dateutil.parser import parse
    from pyfields import field, make_init
    from pylandsat import Product
    from shapely import geometry, wkt, ops
except ImportError as e:
    msg = (
        "ukis_pysat.data dependencies are not installed.\n\n"
        "Please pip install as follows:\n\n"
        "  python -m pip install ukis-pysat[data] --upgrade"
    )
    raise ImportError(str(e) + "\n\n" + msg)

from ukis_pysat.file import env_get, pack
from ukis_pysat.members import Datahub, Platform

logger = logging.getLogger(__name__)


class Source:
    """
    Provides methods to query data sources for metadata and download images and quicklooks (APIs only).
    Remote APIs and local data directories that hold metadata files are supported.
    """

    def __init__(self, datahub, datadir=None, datadir_substr=None):
        """
        :param datahub: Data source (<enum 'Datahub'>).
        :param datadir: Path to directory that holds the metadata if datahub is 'File' (String).
        :param datadir_substr: Optional substring patterns to identify metadata in datadir if datahub
            is 'File' (List of String).
        """
        self.src = datahub

        if self.src == Datahub.File:
            if not datadir:
                raise AttributeError(f"'datadir' has to be set if datahub is 'File'.")
            else:
                self.api = datadir
                if datadir_substr is None:
                    self.api_substr = datadir_substr = [""]
                else:
                    self.api_substr = datadir_substr

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
            raise NotImplementedError(f"{datahub} is not supported [File, EarthExplorer, Scihub]")

    def __enter__(self):
        return self

    def query_metadata(self, platform, date, aoi, cloud_cover=None):
        """Queries satellite image metadata from data source.

        :param platform: Image platform (<enum 'Platform'>).
        :param date: Date from - to (String or Datetime tuple). Expects a tuple of (start, end), e.g.
            (yyyyMMdd, yyyy-MM-ddThh:mm:ssZ, NOW, NOW-<n>DAY(S), HOUR(S), MONTH(S), etc.)
        :param aoi: Area of interest as GeoJson file or bounding box tuple with lat lon coordinates (String, Tuple).
        :param cloud_cover: Percent cloud cover scene from - to (Integer tuple).
        :returns: Metadata of products that match query criteria (List of Metadata objects).
        """
        if self.src == Datahub.File:
            # query Filesystem for metadata
            start_date = sentinelsat.format_query_date(date[0])
            end_date = sentinelsat.format_query_date(date[1])
            geom = self.prep_aoi(aoi)
            if cloud_cover and platform != platform.Sentinel1:
                min_cloud_cover = cloud_cover[0]
                max_cloud_cover = cloud_cover[1]
            else:
                min_cloud_cover = 0
                max_cloud_cover = 100

            # get all json files in datadir that match substr
            meta_files = sorted(
                [
                    os.path.join(dp, f)
                    for dp, dn, filenames in os.walk(self.api)
                    for substr in self.api_substr
                    for f in filenames
                    if f.endswith(".json") and substr in f
                ],
                key=str.lower,
            )

            # filter json files by query parameters
            meta_src = []
            for meta_file in meta_files:
                with open(meta_file) as f:
                    m = json.load(f)
                    try:
                        self.construct_metadata(m)
                    except (json.decoder.JSONDecodeError, LookupError, TypeError) as e:
                        raise ValueError(f"{os.path.basename(meta_file)} not a valid metadata file. {e}.")
                    m_platform = m["properties"]["platformname"]
                    m_date = sentinelsat.format_query_date(m["properties"]["acquisitiondate"])
                    m_geom = geometry.shape(m["geometry"])
                    m_cloud_cover = m["properties"]["cloudcoverpercentage"]
                    if m_cloud_cover is None:
                        m_cloud_cover = 0
                    if (
                        m_platform == platform.value
                        and m_date >= start_date
                        and m_date < end_date
                        and m_geom.intersects(geom)
                        and m_cloud_cover >= min_cloud_cover
                        and m_cloud_cover < max_cloud_cover
                    ):
                        meta_src.append(m)

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

        # construct MetadataCollection from list of Metadata objects
        return MetadataCollection([self.construct_metadata(meta_src=m) for m in meta_src])

    def construct_metadata(self, meta_src):
        """Constructs a metadata object that is harmonized across the different satellite image sources.

        :param meta_src: Source metadata (GeoJSON-like mapping)
        :returns: Harmonized metadata (Metadata object)
        """
        if self.src == Datahub.File:
            meta = Metadata(
                id=meta_src["properties"]["id"],
                platformname=Platform(meta_src["properties"]["platformname"]),
                producttype=meta_src["properties"]["producttype"],
                orbitdirection=meta_src["properties"]["orbitdirection"],
                orbitnumber=int(meta_src["properties"]["orbitnumber"]),
                relativeorbitnumber=int(meta_src["properties"]["relativeorbitnumber"]),
                acquisitiondate=meta_src["properties"]["acquisitiondate"],
                ingestiondate=meta_src["properties"]["ingestiondate"],
                cloudcoverpercentage=meta_src["properties"]["cloudcoverpercentage"],
                format=meta_src["properties"]["format"],
                size=meta_src["properties"]["size"],
                srcid=meta_src["properties"]["srcid"],
                srcurl=meta_src["properties"]["srcurl"],
                srcuuid=meta_src["properties"]["srcuuid"],
                geom=meta_src["geometry"],
            )

        elif self.src == Datahub.EarthExplorer:
            meta = Metadata(
                id=meta_src["displayId"],
                platformname=Platform(
                    meta_src["dataAccessUrl"][
                        meta_src["dataAccessUrl"].find("dataset_name=")
                        + len("dataset_name=") : meta_src["dataAccessUrl"].rfind("&ordered=")
                    ]
                ),
                producttype="L1TP",
                orbitdirection="DESCENDING",
                orbitnumber=int(
                    meta_src["summary"][
                        meta_src["summary"].find("Path: ") + len("Path: ") : meta_src["summary"].rfind(", Row: ")
                    ]
                ),
                relativeorbitnumber=int(meta_src["summary"][meta_src["summary"].find("Row: ") + len("Row: ") :]),
                acquisitiondate=meta_src["acquisitionDate"],
                ingestiondate=meta_src["modifiedDate"],
                cloudcoverpercentage=float(round(meta_src["cloudCover"], 2)) if "cloudCover" in meta_src else None,
                format="GeoTIFF",
                srcid=meta_src["displayId"],
                srcurl=meta_src["dataAccessUrl"],
                srcuuid=meta_src["entityId"],
                geom=meta_src["spatialFootprint"],
            )

        else:
            meta = Metadata(
                id=meta_src["properties"]["identifier"],
                platformname=Platform(meta_src["properties"]["platformname"]),
                producttype=meta_src["properties"]["producttype"],
                orbitdirection=meta_src["properties"]["orbitdirection"],
                orbitnumber=int(meta_src["properties"]["orbitnumber"]),
                relativeorbitnumber=int(meta_src["properties"]["relativeorbitnumber"]),
                acquisitiondate=meta_src["properties"]["beginposition"],
                ingestiondate=meta_src["properties"]["ingestiondate"],
                cloudcoverpercentage=float(round(meta_src["properties"]["cloudcoverpercentage"], 2))
                if "cloudcoverpercentage" in meta_src["properties"]
                else None,
                format=meta_src["properties"]["format"],
                size=meta_src["properties"]["size"],
                srcid=meta_src["properties"]["identifier"],
                srcurl=meta_src["properties"]["link"],
                srcuuid=meta_src["properties"]["uuid"],
                geom=meta_src["geometry"],
            )

        return meta

    def download_image(self, platform, product_uuid, target_dir):
        """Downloads satellite image data to a target directory for a specific product_id.
        Incomplete downloads are continued and complete files are skipped.

        :param platform: Image platform (<enum 'Platform'>).
        :param product_uuid: UUID of the satellite image product (String).
        :param target_dir: Target directory that holds the downloaded images (String)
        """
        if self.src == Datahub.File:
            raise Exception("download_image not supported for {self.src}.")

        elif self.src == Datahub.EarthExplorer:
            # query EarthExplorer for srcid of product
            meta_src = self.api.request("metadata", **{"datasetName": platform.value, "entityIds": [product_uuid],},)
            product_srcid = meta_src[0]["displayId"]
            # download data from AWS
            product = Product(product_srcid)
            product.download(out_dir=target_dir, progressbar=False)

            # compress download directory and remove original files
            pack(
                os.path.join(target_dir, product_srcid), root_dir=os.path.join(target_dir, product_srcid),
            )
            shutil.rmtree(os.path.join(target_dir, product_srcid))

        else:
            self.api.download(product_uuid, target_dir, checksum=True)

    def download_quicklook(self, platform, product_uuid, target_dir):
        """Downloads a quicklook of the satellite image to a target directory for a specific product_id.
        It performs a very rough geocoding of the quicklooks by shifting the image to the location of the footprint.

        :param platform: Image platform (<enum 'Platform'>).
        :param product_uuid: UUID of the satellite image product (String).
        :param target_dir: Target directory that holds the downloaded images (String)
        """
        if self.src == Datahub.File:
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
        Image.fromarray(quicklook).save(os.path.join(target_dir, product_srcid + ".jpg"))

        # geocode quicklook
        quicklook_size = (quicklook.shape[1], quicklook.shape[0])
        dist_x = geometry.Point(bounds[0], bounds[1]).distance(geometry.Point(bounds[2], bounds[1])) / quicklook_size[0]
        dist_y = geometry.Point(bounds[0], bounds[1]).distance(geometry.Point(bounds[0], bounds[3])) / quicklook_size[1]
        ul_x, ul_y = bounds[0], bounds[3]
        with open(os.path.join(os.path.join(target_dir, product_srcid + ".jpgw")), "w") as out_file:
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
        # this could include both fiel paths and WKT strings
        if isinstance(aoi, str):
            # check if handed object is a file
            if os.path.isfile(aoi):
                with fiona.open(aoi, "r") as aoi:
                    # make sure crs is in epsg:4326
                    project = pyproj.Transformer.from_proj(
                        proj_from=pyproj.Proj(aoi.crs["init"]),
                        proj_to=pyproj.Proj("epsg:4326"),
                        skip_equivalent=True,
                        always_xy=True,
                    )
                    aoi = ops.transform(project.transform, geometry.shape(aoi[0]["geometry"]))

            elif wkt.loads(aoi):
                aoi = wkt.loads(aoi)

            else:
                raise ValueError(f"aoi must be a filepath or a WKT string")

        elif isinstance(aoi, tuple):
            aoi = geometry.box(aoi[0], aoi[1], aoi[2], aoi[3])

        else:
            raise TypeError(f"aoi must be of type string or tuple")

        return aoi

    def close(self):
        """Closes connection to or logs out of Datahub"""
        if self.src == Datahub.EarthExplorer:
            self.api.logout()
        elif self.src == Datahub.Scihub:
            self.api.session.close()
        else:
            pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class Metadata:
    """
    Provides a container to store metadata. Fields are assigned a default value, checked for dtype, validated
    and converted if needed.
    """

    __init__ = make_init()
    id: str = field(check_type=True, read_only=True, doc="Product ID")
    platformname: Platform = field(check_type=True, default=None, doc="Platform name")
    producttype: str = field(check_type=True, default="", doc="Product type")
    orbitdirection: str = field(check_type=True, default="", doc="Orbitdirection")
    orbitnumber: int = field(check_type=True, default=None, doc="Orbitnumber")
    relativeorbitnumber: int = field(check_type=True, default=None, doc="Relative orbitnumber")
    acquisitiondate = field(type_hint=datetime.date, check_type=True, default=None, doc="Acquisitiondate")
    ingestiondate = field(type_hint=datetime.date, check_type=True, default=None, doc="Ingestiondate")
    processingdate = field(type_hint=datetime.date, check_type=True, default=None, doc="Processingdate")
    processingsteps: str = field(check_type=True, default="", doc="Processingsteps")
    processingversion: str = field(check_type=True, default="", doc="Processing version")
    bandlist: str = field(check_type=True, default="", doc="Bandlist")
    cloudcoverpercentage: float = field(check_type=True, default=None, doc="Cloudcover [percent]")
    format: str = field(check_type=True, default="", doc="File format")
    size: str = field(check_type=True, default="", doc="File size [MB]")
    srcid: str = field(check_type=True, doc="Source product ID")
    srcurl: str = field(check_type=True, default="", doc="Source product URL")
    srcuuid: str = field(check_type=True, doc="Source product UUID")
    geom: dict = field(check_type=True, default=None, doc="Geometry [multipolygon dict]")

    @acquisitiondate.converter(accepts=str)
    @ingestiondate.converter(accepts=str)
    @processingdate.converter(accepts=str)
    def _prep_date(self, value):
        """Converts a date string to datetime.date object.

        :returns: Datetime.date
        """
        if value is not None:
            return parse(value)

    def to_dict(self):
        """Converts Metadata to Dict.

        :returns: Metadata (Dict)
        """
        return {
            "id": self.id,
            "platformname": None if self.platformname is None else self.platformname.value,
            "producttype": self.producttype,
            "orbitdirection": self.orbitdirection,
            "orbitnumber": self.orbitnumber,
            "relativeorbitnumber": self.relativeorbitnumber,
            "acquisitiondate": None if self.acquisitiondate is None else self.acquisitiondate.strftime("%Y/%m/%d"),
            "ingestiondate": None if self.ingestiondate is None else self.ingestiondate.strftime("%Y/%m/%d"),
            "processingdate": None if self.processingdate is None else self.processingdate.strftime("%Y/%m/%d"),
            "processingsteps": self.processingsteps,
            "processingversion": self.processingversion,
            "bandlist": self.bandlist,
            "cloudcoverpercentage": self.cloudcoverpercentage,
            "format": self.format,
            "size": self.size,
            "srcid": self.srcid,
            "srcurl": self.srcurl,
            "srcuuid": self.srcuuid,
        }

    def to_json(self):
        """Converts Metadata to JSON.

        :returns: Metadata (JSON)
        """
        return json.dumps(self.to_dict())

    def to_geojson(self):
        """Converts Metadata to GeoJSON.

        :returns: Metadata (GeoJSON)
        """
        return geometry.mapping(_GeoInterface({"type": "Feature", "properties": self.to_dict(), "geometry": self.geom}))

    def save(self, target_dir):
        """Saves Metadata to GeoJSON file in target_dir with srcid as filename.

        :param target_dir: Target directory that holds the downloaded metadata (String)
        """
        g = self.to_geojson()
        with open(os.path.join(target_dir, g["properties"]["srcid"] + ".json"), "w") as f:
            json.dump(g, f)


class MetadataCollection:
    """
    Provides a container to store a collection of Metadata objects. Conversion methods are provided to
    analyse the MetadataCollection further.
    """

    __init__ = make_init()
    items: List[Metadata] = field(doc="Collection of Metadata objects")

    def to_dict(self):
        """Converts MetadataCollection to List of Dict.

        :returns: MetadataCollection (List of Dict)
        """
        return [item.to_dict() for item in self.items]

    def to_json(self):
        """Converts MetadataCollection to List of JSON.

        :returns: MetadataCollection (List of JSON)
        """
        return [item.to_json() for item in self.items]

    def to_geojson(self):
        """Converts MetadataCollection to list of GeoJSON.

        :returns: MetadataCollection (List of GeoJSON)
        """
        return [item.to_geojson() for item in self.items]

    def to_pandas(self):
        """Converts MetadataCollection to Pandas Dataframe.

        :returns: MetadataCollection (Pandas Dataframe)
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("to_pandas requires optional dependency Pandas.")

        d = [item.to_dict() for item in self.items]
        return pd.DataFrame(d)

    def filter(self, filter_dict):
        """Filters MetadataCollection based on filter_dict.

        :param filter_dict: Key value pair to use as filter e.g. {"producttype": "S2MSI1C"} (Dictionary).
        :returns: self
        """
        k = list(filter_dict.keys())[0]
        self.items = [item for item in self.items if filter_dict[k] == item.to_geojson()["properties"][k]]
        return self

    def save(self, target_dir):
        """Saves MetadataCollection to GeoJSON files in target_dir with srcid as filenames.

        :param target_dir: Target directory (String)
        """
        for item in self.items:
            item.save(target_dir)


class _GeoInterface(object):
    def __init__(self, d):
        self.__geo_interface__ = d


if __name__ == "__main__":
    pass
