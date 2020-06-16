#!/usr/bin/env python3

import contextlib
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone


def env_get(key):
    """get an environment variable or fail with a meaningful error message"""
    try:
        return os.environ[key]
    except KeyError:
        raise KeyError(f"No environment variable {key} found")


def unpack(filename, extract_dir=None):
    """Unpack an archive, does not add anything to shutil, but makes aware it exists.

    :param filename: full path of the archive
    :param extract_dir: name of the target directory where the archive is unpacked. If not provided, the current working directory is used.
    """
    if extract_dir:
        shutil.unpack_archive(filename, extract_dir)
    else:
        shutil.unpack_archive(filename)


def pack(base_name, root_dir, fformat="zip"):
    """Create an archive file (such as zip or tar) and return its name. Does not add anything to shutil,
    but makes aware it exists.

    :param base_name: name of the file to create, including the path, minus any format-specific extension
    :param root_dir: directory that will be the root directory of the archive
    :param fformat: archive format: "zip", "tar", "gztar"
    :return: name of archive file
    """
    return shutil.make_archive(base_name, format=fformat, root_dir=root_dir)


@contextlib.contextmanager
def get_sentinel_scene_from_dir(indir):
    """Scan directory for s1 scenes, unzips them if necessary. Tested with Sentinel-1, -2 & -3.

    :param indir: path to zipped S1 scene or directory with S1 scene
    :yields: full_path (directory with scene, str), ident (filename of scene, str)

    >>> with get_sentinel_scene_from_dir(os.path.join(r"..", "tests", "testfiles")) as (full_path, ident):
    ...     print(ident)
    S1M_hello_from_inside
    """
    pattern = re.compile("^S[1-3]._+")

    for entry in os.listdir(indir):
        full_path = os.path.join(indir, entry)

        ident = os.path.splitext(os.path.basename(full_path))[0]
        if not pattern.match(ident):
            continue

        if full_path.endswith(".zip"):
            cwd = os.getcwd()
            scene_zip = os.path.abspath(full_path)
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                try:
                    with zipfile.ZipFile(scene_zip) as z:
                        z.extractall()
                        with get_sentinel_scene_from_dir(td) as res:
                            yield res
                finally:
                    os.chdir(cwd)
        elif os.path.isdir(full_path):
            yield full_path, ident


def get_polarization_from_s1_filename(filename, dual=False):
    """Get polarization from the filename of a Sentinel-1 scene.
    https://sentinel.esa.int/web/sentinel/user-guides/sentinel-1-sar/naming-conventions.

    :param filename: top-level SENTINEL-1 product folder name
    :param dual: boolean (default: True), optional
    :return: str or list

    >>> get_polarization_from_s1_filename("MMM_BB_TTTR_1SDH_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip")
    'HH'
    >>> get_polarization_from_s1_filename("MMM_BB_TTTR_1SSH_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip")
    'HH'
    >>> get_polarization_from_s1_filename("MMM_BB_TTTR_2SSV_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip")
    'VV'
    >>> get_polarization_from_s1_filename("MMM_BB_TTTR_1SDV_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip", True)
    ['VV', 'VH']
    """
    polarization_dict = {
        "SSV": "VV",
        "SSH": "HH",
        "SDV": ["VV", "VH"],
        "SDH": ["HH", "HV"],
    }

    polarization = polarization_dict[filename[13:16]]
    if not dual and isinstance(polarization, list):
        return polarization[0]
    else:
        return polarization


def get_ts_from_sentinel_filename(filename, start_date=True):
    """Get timestamp from the filename of a Sentinel scene, according to naming conventions.
    Currently works for S1, S2 & S3.

    :param  filename: top-level SENTINEL product folder or file name
    :param start_date: boolean (default: True), False is Stop Date, optional
    :return: datetime.datetime object with timezone information

    >>> get_ts_from_sentinel_filename("S1M_BB_TTTR_LFPP_20200113T074619_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.SAFE.zip")
    datetime.datetime(2020, 1, 13, 7, 46, 19, tzinfo=datetime.timezone.utc)
    >>> get_ts_from_sentinel_filename("S1M_BB_TTTR_LFPP_YYYYMMDDTHHMMSS_20200113T002219_OOOOOO_DDDDDD_CCCC.SAFE.zip", False)
    datetime.datetime(2020, 1, 13, 0, 22, 19, tzinfo=datetime.timezone.utc)
    >>> get_ts_from_sentinel_filename("S3M_OL_L_TTT____20200113T074619_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_i_GGG_c.SEN3")
    datetime.datetime(2020, 1, 13, 7, 46, 19, tzinfo=datetime.timezone.utc)
    >>> get_ts_from_sentinel_filename("S3M_OL_L_TTTTTT_yyyymmddThhmmss_20200113T074619_YYYYMMDDTHHMMSS_i_GGG_c.SEN3", False)
    datetime.datetime(2020, 1, 13, 7, 46, 19, tzinfo=datetime.timezone.utc)
    >>> get_ts_from_sentinel_filename("S2AM_MSIXXX_20200113T074619_Nxxyy_ROOO_Txxxxx_<Product Discriminator>.SAFE")
    datetime.datetime(2020, 1, 13, 7, 46, 19, tzinfo=datetime.timezone.utc)
    """
    if filename.startswith("S2"):
        return datetime.strptime(filename.split("_")[2], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    elif filename.startswith("S1"):
        if start_date:
            return datetime.strptime(filename.split("_")[4], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        else:
            return datetime.strptime(filename.split("_")[5], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    else:
        if start_date:
            return datetime.strptime(filename[16:31], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        else:
            return datetime.strptime(filename[32:47], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def get_footprint_from_manifest(xml_path):
    """Return a shapely polygon with footprint of scene, tested for Sentinel-1.

    :param xml_path: path to manifest.safe
    :return: shapely polygon

    >>> get_footprint_from_manifest(os.path.join(r"../tests/testfiles/", "manifest.safe")).wkt
    'POLYGON ((149.766922 -24.439564, 153.728622 -23.51771, 154.075058 -24.737713, 150.077042 -25.668921, 149.766922 -24.439564))'
    """
    try:
        from shapely.geometry import Polygon
    except ImportError:
        raise ImportError("get_footprint_from_manifest requires optional dependency Shapely.")
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for elem in root.iter("metadataSection"):
        for child in elem.iter():
            if child.tag == "{http://www.opengis.net/gml}coordinates":
                coords = child.text

                vertices = []
                for i in coords.split(" "):
                    i = i.split(",")
                    vertices.append((float(i[1]), float(i[0])))
                return Polygon(vertices)


def get_origin_from_manifest(xml_path):
    """Get origin from manifest file, tested for Sentinel-1.

    :param xml_path: path to manifest.safe
    :return: country of origin

    >>> get_origin_from_manifest(os.path.join(r"../tests/testfiles/", "manifest.safe"))
    'United Kingdom'
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for elem in root.iter("metadataSection"):
        for child in elem.iter():
            if child.tag == "{http://www.esa.int/safe/sentinel-1.0}facility":
                return child.attrib["country"]


def get_ipf_from_manifest(xml_path):
    """Get IPF version from manifest file, tested for Sentinel-1.

    :param xml_path: path to manifest.safe
    :return: ipf version (float)

    >>> get_ipf_from_manifest(os.path.join(r"../tests/testfiles/", "manifest.safe"))
    2.82
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for elem in root.iter("metadataSection"):
        for child in elem.iter():
            if child.tag == "{http://www.esa.int/safe/sentinel-1.0}software":
                return float(child.attrib["version"])


def get_pixel_spacing(scenedir, polarization="HH"):
    """Get pixel spacing, tested for Sentinel-1.

    :param scenedir: path to unzipped SAFE-directory of scene
    :param polarization: str (default: 'HH')
    :return: tuple with pixel spacing in meters and degrees as floats

    >>> get_pixel_spacing(r"../tests/testfiles/")
    (40.0, 0.0003593261136478086)
    """
    for entry in os.listdir(os.path.join(scenedir, "annotation")):
        if entry.endswith(".xml") and entry.split("-")[3] == polarization.lower():
            tree = ET.parse(os.path.join(scenedir, "annotation", entry))
            root = tree.getroot()
            for elem in root.iter("imageInformation"):
                for child in elem.iter():
                    if child.tag == "rangePixelSpacing":
                        pixel_spacing_meter = float(child.text)
                        pixel_spacing_degree = (pixel_spacing_meter / 10.0) * 8.983152841195215e-5

                        return pixel_spacing_meter, pixel_spacing_degree


def get_proj_string(footprint):
    """Get UTM projection string the centroid of footprint is located in. Footprint itself might cover multiple UTM
    zones.

    :param footprint: shapely polygon
    :return: string with information about projection

    >>> get_proj_string(get_footprint_from_manifest(r"../tests/testfiles/"))
    +proj=utm +zone=56J, +ellps=WGS84 +datum=WGS84 +units=m +no_defs
    """
    try:
        import utm
    except ImportError:
        raise ImportError("get_proj_string requires optional dependency utm.")
    # get UTM coordinates from Lat/lon pair of centroid of footprint
    # coords contains UTM coordinates, UTM zone & UTM letter, e.g. (675539.8854425425, 4478111.711657521, 34, 'T')
    coords = utm.from_latlon(footprint.centroid.y, footprint.centroid.x)

    return f"+proj=utm +zone={coords[2]}{coords[3]}, +ellps=WGS84 +datum=WGS84 +units=m +no_defs"


if __name__ == "__main__":
    import doctest

    doctest.testmod()
