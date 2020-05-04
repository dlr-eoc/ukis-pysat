#!/usr/bin/env python3

import json
import logging
import os
import shutil
import traceback

import landsatxplore.api
import requests
import sentinelsat
from matplotlib.pyplot import imread
from pylandsat import Product
from shapely import geometry, wkt

from ukis_pysat.members import Datahub
from ukis_pysat.file import env_get, pack

logger = logging.getLogger(__name__)


class Source:
    """
    This class provides methods to query data sources for metadata and download images (APIs only).
    Remote APIs and local data directories that hold metadata files are supported.
    """

    def __init__(self, source, source_dir=None):
        """
        :param source: Name of the data source ['file', 'scihub', 'earthexplorer'] (String).
        :param source_dir: Path to directory if source is 'file' (String).
        """
        self.src = source

        if self.src == Datahub.file:
            if not source_dir:
                raise Exception(f"{traceback.format_exc()} source_dir has to be set if source is {self.src}.")
            else:
                self.api = source_dir

        elif self.src == Datahub.EarthExplorer:
            try:
                self.user = env_get("EARTHEXPLORER_USER")
                self.pw = env_get("EARTHEXPLORER_PW")
                self.api = landsatxplore.api.API(self.user, self.pw)
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not connect to EarthExplorer. This Exception was raised {e}."
                )

        elif self.src == Datahub.Scihub:
            try:
                self.user = env_get("SCIHUB_USER")
                self.pw = env_get("SCIHUB_PW")
                self.api = sentinelsat.SentinelAPI(
                    self.user, self.pw, "https://scihub.copernicus.eu/dhus", show_progressbars=False,
                )
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not connect to SciHub. This Exception was raised: {e}."
                )
        else:
            raise NotImplementedError(f"{source} is not supported [file, earthexplorer, scihub]")

    def __enter__(self):
        return self

    def query(self, aoi, platform, date, cloud_cover=None):
        """This method queries satellite image metadata either online or on a local file directory.

        :param aoi: Area of interest in WGS84 (GeoJson).
        :param platform: image platform (<enum 'Platform'>).
        :param date: Date from - to (String or Datetime tuple). Expects a tuple of (start, end), e.g.
            (yyyyMMdd, yyyy-MM-ddThh:mm:ssZ, NOW, NOW-<n>DAY(S), HOUR(S), MONTH(S), etc.)

        :param cloud_cover: Percent cloud cover scene from - to (Integer tuple).
        :returns: Metadata of products that match query criteria (GeoJSON-like mapping).
        """
        if self.src == Datahub.file:
            raise NotImplementedError("File metadata query not yet supported.")
        elif self.src == Datahub.EarthExplorer:
            try:
                bbox = geometry.shape(sentinelsat.read_geojson(aoi)[0]["geometry"]).bounds
                if not cloud_cover:
                    # query Earthexplorer for metadata without cloudcoverpercentage
                    meta_src = self.api.search(
                        dataset=platform.value,
                        bbox=[bbox[1], bbox[0], bbox[3], bbox[2]],
                        start_date=sentinelsat.format_query_date(date[0]),
                        end_date=sentinelsat.format_query_date(date[1]),
                        max_results=10000,
                    )
                else:
                    # query Earthexplorer for metadata with cloudcoverpercentage
                    meta_src = self.api.search(
                        dataset=platform.value,
                        bbox=[bbox[1], bbox[0], bbox[3], bbox[2]],
                        start_date=sentinelsat.format_query_date(date[0]),
                        end_date=sentinelsat.format_query_date(date[1]),
                        max_cloud_cover=cloud_cover[1],
                        max_results=10000,
                    )
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not execute query to EarthExplorer. Check your query parameters. "
                    f"The following Exception was raised: {e}."
                )

            try:
                for m in meta_src:
                    try:
                        # check if cloudcoverpercentage exists
                        cloudcoverpercentage = m["cloudCover"]
                    except KeyError:
                        cloudcoverpercentage = ""  # leave it empty if not exists
                    # convert metadata to custom metadata
                    return self._construct_metadata(
                        id=m["displayId"],
                        platformname=platform,
                        producttype="L1TP",
                        orbitdirection="DESCENDING",
                        orbitnumber=m["summary"][
                            m["summary"].find("Path: ") + len("Path: ") : m["summary"].rfind(", Row: ")
                        ],
                        relativeorbitnumber=m["summary"][m["summary"].find("Row: ") + len("Row: ") :],
                        acquisitiondate=m["acquisitionDate"],
                        ingestiondate=m["modifiedDate"],
                        processingdate="",
                        processingsteps="",
                        processingversion="",
                        bandlist=[{}],
                        cloudcoverpercentage=cloudcoverpercentage,
                        format="GeoTIFF",
                        size="",
                        srcid=m["displayId"],
                        srcurl=m["dataAccessUrl"],
                        srcuuid=m["entityId"],
                        geom=m["spatialFootprint"],
                    )
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not convert metadata to custom metadata. "
                    f"The following Exception was raised: {e}."
                )

        elif self.src == Datahub.Scihub:
            try:
                if not cloud_cover or platform == platform.Sentinel1:
                    # query Scihub for metadata without cloudcoverpercentage
                    meta_src = self.api.query(
                        area=sentinelsat.geojson_to_wkt(sentinelsat.read_geojson(aoi)),
                        date=date,
                        platformname=platform.value,
                    )
                else:
                    # query Scihub for metadata with cloudcoverpercentage
                    meta_src = self.api.query(
                        area=sentinelsat.geojson_to_wkt(sentinelsat.read_geojson(aoi)),
                        date=date,
                        platformname=platform.value,
                        cloudcoverpercentage=cloud_cover,
                    )
                meta_src = self.api.to_geojson(meta_src)
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not execute query to Scihub. Check your query parameters."
                    f"The following Exception was raised: {e}."
                )

            try:
                for i in range(len(meta_src["features"])):
                    try:
                        # check if cloudcoverpercentage exists
                        cloudcoverpercentage = meta_src["features"][i]["properties"]["cloudcoverpercentage"]
                    except KeyError:
                        cloudcoverpercentage = ""  # leave it empty if not exists
                    # convert Scihub metadata to custom metadata
                    return self._construct_metadata(
                        id=meta_src["features"][i]["properties"]["identifier"],
                        platformname=meta_src["features"][i]["properties"]["platformname"],
                        producttype=meta_src["features"][i]["properties"]["producttype"],
                        orbitdirection=meta_src["features"][i]["properties"]["orbitdirection"],
                        orbitnumber=meta_src["features"][i]["properties"]["orbitnumber"],
                        relativeorbitnumber=meta_src["features"][i]["properties"]["relativeorbitnumber"],
                        acquisitiondate=meta_src["features"][i]["properties"]["beginposition"],
                        ingestiondate=meta_src["features"][i]["properties"]["ingestiondate"],
                        processingdate="",
                        processingsteps="",
                        processingversion="",
                        bandlist=[{}],
                        cloudcoverpercentage=cloudcoverpercentage,
                        format=meta_src["features"][i]["properties"]["format"],
                        size=meta_src["features"][i]["properties"]["size"],
                        srcid=meta_src["features"][i]["properties"]["identifier"],
                        srcurl=meta_src["features"][i]["properties"]["link"],
                        srcuuid=meta_src["features"][i]["properties"]["uuid"],
                        geom=meta_src["features"][i]["geometry"],
                    )
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not convert metadata to custom metadata. "
                    f"The following Exception was raised: {e}."
                )

    @staticmethod
    def _construct_metadata(geom, **kwargs):
        """This method puts satellite image metadata into __geo_interface__ https://gist.github.com/sgillies/2217756
        Example Metadata: tests/testfiles/S2A_MSIL2A_20200221T102041_N0214_R065_T32UQC_20200221T120618.json

        :param geom: geometry in GeoJSON-format
        :returns: Metadata of satellite product (GeoJSON-like mapping)
        """
        return geometry.mapping(_GeoInterface({"type": "Feature", "properties": kwargs, "geometry": geom}))

    def get_metadata(self, product_id):
        """This method gets satellite image metadata for a specific product from a local file directory.

        :param product_id: ID of the satellite image product (String).
        :returns: Metadata of satellite product that matches the product_id (GeoJson).
        """
        if self.src == Datahub.file:
            # search local directory for metadata of a particular image
            for root, dirs, files in os.walk(str(self.api)):
                for file in files:
                    if file.endswith(".json") and product_id in file:
                        with open(os.path.join(root, file)) as json_file:
                            return json.load(json_file)

        elif self.src == Datahub.EarthExplorer:
            raise NotImplementedError(f"get_metadata not supported for {self.src}.")

        elif self.src == Datahub.Scihub:
            raise NotImplementedError(f"get_metadata not supported for {self.src}.")

    def download_image(self, product_srcid, product_uuid, target_dir):
        """This method downloads satellite image data to a target directory for a specific product_id.
        Incomplete downloads are continued and complete files are skipped.

        :param product_srcid: Product source id (String).
        :param product_uuid: UUID of the satellite image product (String).
        :param target_dir: Target directory that holds the downloaded images (String)
        """
        if self.src == Datahub.file:
            logger.warning(f"download_image not supported for {self.src}.")

        elif self.src == Datahub.EarthExplorer:
            try:
                # NOTE: this downloads data from Amazon AWS using pylandsat. landsatxplore is great for metadata
                # search on EE but download via EE is slow. pylandsat is great for fast download from AWS but is
                # poor for metadata search. Here we combine them to get the best from both packages.
                product = Product(product_srcid)
                product.download(out_dir=target_dir, progressbar=False)
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not download data through {self.src} (stored on AWS). "
                    f"The following Exception was raised: {e}."
                )
            try:
                # compress download directory and remove original files
                pack(
                    os.path.join(target_dir, product_srcid), root_dir=os.path.join(target_dir, product_srcid),
                )
                shutil.rmtree(os.path.join(target_dir, product_srcid))
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not download data through {self.src}. "
                    f"This Exception was raised: {e}."
                )

        elif self.src == Datahub.Scihub:
            try:
                self.api.download(product_uuid, target_dir, checksum=True)
            except Exception as e:
                raise Exception(
                    f"{traceback.format_exc()} Could not download data through {self.src}. "
                    f"This Exception was raised: {e}."
                )

    def download_quicklook(self, platform, product_uuid, product_srcid, target_dir):
        """This method downloads a quicklook of the satellite image to a target directory for a specific product_id.

        :param platform: image platform (<enum 'Platform'>).
        :param product_uuid: UUID of the satellite image product (String).
        :param product_srcid: Product source id (String).
        :param target_dir: Target directory that holds the downloaded images (String)
        """
        if self.src == Datahub.file:
            logger.warning(f"download_quicklook not supported for {self.src}.")
            return

        elif self.src == Datahub.EarthExplorer:
            try:
                m = self.api.request("metadata", **{"datasetName": platform.value, "entityIds": [product_uuid],},)
                url = m[0]["browseUrl"]
                bounds = geometry.shape(m[0]["spatialFootprint"]).bounds
                self.save_quicklook_image(url, bounds, product_srcid, target_dir)
            except Exception as e:
                logger.warning(
                    f"{traceback.format_exc()} Could not download and save quicklook. "
                    f"This Exception was raised: {e}."
                )

        elif self.src == Datahub.Scihub:
            try:
                m = self.api.get_product_odata(product_uuid)
                url = "https://scihub.copernicus.eu/apihub/odata/v1/Products('{}')/Products('Quicklook')/$value".format(
                    product_uuid
                )
                bounds = wkt.loads(m["footprint"]).bounds
                self.save_quicklook_image(url, bounds, product_srcid, target_dir)
            except Exception as e:
                logger.warning(
                    f"{traceback.format_exc()} Could not download and save quicklook. This Exception was raised: {e}."
                )

    def save_quicklook_image(self, platform, bounds, product_srcid, target_dir):
        """This method saves a quicklook of the satellite image to a target directory for a specific product_id.

        :param platform: image platform (<enum 'Platform'>).
        :param bounds: Bounding Box of footprint
        :param product_srcid: Product source id (String).
        :param target_dir: Target directory that holds the downloaded images (String)
        """
        response = requests.get(platform, auth=(self.user, self.pw))
        with open(os.path.join(target_dir, product_srcid + ".jpg"), "wb") as f:
            f.write(response.content)
        quicklook = imread(os.path.join(target_dir, product_srcid + ".jpg"))
        quicklook_size = (quicklook.shape[1], quicklook.shape[0])

        # save worldfile
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

    def close(self):
        """closes connection to or logs out of Datahub"""
        if self.src == Datahub.EarthExplorer:
            self.api.logout()
        elif self.src == Datahub.Scihub:
            self.api.session.close()
        else:
            pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class _GeoInterface(object):
    def __init__(self, d):
        self.__geo_interface__ = d


if __name__ == "__main__":
    pass
