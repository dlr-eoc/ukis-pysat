import hashlib
import os
from datetime import datetime

import requests
from tqdm import tqdm

from ukis_pysat.members import Bands

"""Extracted from the pylandsat"""
"""https://github.com/yannforget/pylandsat"""


def meta_from_pid(product_id):
    """Extract metadata contained in a Landsat Product Identifier."""
    meta = {}
    parts = product_id.split("_")
    meta["product_id"] = product_id
    meta["sensor"], meta["correction"] = parts[0], parts[1]
    meta["path"], meta["row"] = int(parts[2][:3]), int(parts[2][3:])
    meta["acquisition_date"] = datetime.strptime(parts[3], "%Y%m%d")
    meta["processing_date"] = datetime.strptime(parts[4], "%Y%m%d")
    meta["collection"], meta["tier"] = int(parts[5]), parts[6]
    return meta


def compute_md5(fpath):
    """Get hexadecimal MD5 hash of a file."""
    with open(fpath, "rb") as f:
        h = hashlib.md5(f.read())
    return h.hexdigest()


def download_files(url, out_dir, progressbar=False, verify=False):
    """Download a file from an URL into a given directory.


    :param url : str
        File to download.
    :param out_dir : str
        Path to output directory.
    :param progressbar : bool, optional
        Display a progress bar.
    :param verify : bool, optional
        Check that remote and local MD5 hashes are equal.

    :returns fpath : str
        Path to downloaded file.
    """

    fname = url.split("/")[-1]
    fpath = os.path.join(out_dir, fname)
    r = requests.get(url, stream=True)
    remotesize = int(r.headers.get("Content-Length", 0))
    etag = r.headers.get("ETag", "").replace('"', "")

    if r.status_code != 200:
        raise requests.exceptions.HTTPError(str(r.status_code))

    if os.path.isfile(fpath) and os.path.getsize(fpath) == remotesize:
        return fpath
    if progressbar:
        progress = tqdm(total=remotesize, unit="B", unit_scale=True)
        progress.set_description(fname)
    with open(fpath, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                if progressbar:
                    progress.update(1024 * 1024)

    r.close()
    if progressbar:
        progress.close()

    if verify:
        if not compute_md5(fpath) == etag:
            raise requests.exceptions.HTTPError("Download corrupted.")

    return fpath


class Product:
    """It provides methods for checking the list of the available Geotiff Landsat bands  and download them  by
    using the product_id and base_url"""

    def __init__(self, product_id):
        """Initialize a product download.

        :param product_id : str
            Landsat product identifier.
        """

        base_url = (
            "https://storage.googleapis.com/gcp-public-data-landsat/"
            "{sensor}/{collection:02}/{path:03}/{row:03}/{product_id}/"
        )

        self.product_id = product_id
        self.meta = meta_from_pid(product_id)
        self.baseurl = base_url.format(**self.meta)

    @property
    def available(self):
        """List all available files."""
        bands = Bands()
        labels = bands.dict()
        return labels[self.meta["sensor"]]

    def _url(self, label):
        """Get download URL of a given file according to its label."""
        if "README" in label:
            basename = label
        else:
            basename = self.product_id + "_" + label
        return self.baseurl + basename

    def download(self, out_dir, progressbar=True, files=None, verify=True):
        """Download a Landsat product.

        :param out_dir : str
            Path to output directory. A subdirectory named after the
            product ID will automatically be created.
        :param progressbar : bool, optional
            Show a progress bar.
        :param files :: list of str, optional
            Specify the files to download manually. By default, all available
            files will be downloaded.
        :param verify : bool, optional
            Check downloaded files for corruption (True by default).
        """
        dst_dir = os.path.join(out_dir, self.product_id)
        os.makedirs(dst_dir, exist_ok=True)
        if not files:
            files = self.available
        else:
            files = [f for f in files if f in self.available]

        for label in files:
            if ".tif" in label:
                label = label.replace(".tif", ".TIF")
            url = self._url(label)
            download_files(url, dst_dir, progressbar=progressbar, verify=verify)
