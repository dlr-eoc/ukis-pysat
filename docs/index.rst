.. ukis-pysat documentation master file, created by
   sphinx-quickstart on Mon Apr 20 11:21:17 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to UKIS-pysat's documentation!
======================================

The UKIS-pysat package provides generic classes and functions to query, access and process multi-spectral and SAR satellite images.

data
____
Download satellites data from different sources (currently Earth Explorer, SciHub, STAC), deal with and structure metadata.

file
____
Work with you local satellite data files and read information out of file names and metadata files. Currently, focusing on Sentinel-1.

raster
______
Reading satellite data and performing simple, but cumbersome tasks. This is just a layer on top of `rasterio <https://github.com/mapbox/rasterio>`__ for stuff we often need. It can very well be that using *rasterio* directly is often the better choice.

Example
_______
Here's an example about some basic features:
.. code-block:: python

  from ukis_pysat.data import Source
  from ukis_pysat.raster import Image
  from ukis_pysat.file import get_sentinel_scene_from_dir
  from ukis_pysat.members import Datahub, Platform


  # connect to Scihub and query metadata (returns MetadataCollection)
  src = Source(source=Datahub.Scihub)
  meta = src.query_metadata(
      platform=Platform.Sentinel2,
      date=("20200101", "NOW"),
      aoi=(11.90, 51.46, 11.94, 51.50),
      cloud_cover=(0, 50),
  )

  # filter MetadataCollection by producttype
  meta.filter(filter_dict={"producttype": "S2MSI1C"})

  # inspect MetadataCollection with Pandas
  meta_df = meta.to_pandas()
  print(meta_df[["srcid", "producttype", "cloudcoverpercentage", "size", "srcuuid"]])

  # save Metadata item as GeoJSON
  meta.items[0].save(target_dir="target_dir/")

  # download geocoded quicklook
  uuid = meta.items[0].to_dict()["srcuuid"]
  src.download_quicklook(platform=Platform.Sentinel2, product_uuid=uuid, target_dir="target_dir/")

  # download image
  src.download_image(platform=Platform.Sentinel2, product_uuid=uuid, target_dir="target_dir/")

  # get sentinel scene from directory
  with get_sentinel_scene_from_dir(target_dir) as (full_path, ident):
      # initialize an image object
      # keep the dimension order in mind (order of channels or bands)
      with Image(full_path.join('pre_nrcs.tif')) as img:
          # scale the image array, having one band
          img.arr = img.arr * 0.3

Dimension order
---------------
The dimension order can be set upon initialization and you have to choose between *first* (bands, rows, columns), being raster shape needed for rasterio, or *last* (rows, columns, bands), being image shape used by most image processing libraries. Default is *first*.
Compare with the `documentation of rasterio <https://rasterio.readthedocs.io/en/latest/api/rasterio.plot.html#rasterio.plot.reshape_as_image>`__. UKIS-pysat uses rasterio internally and the dimension order is always reshaped to *first* (bands, rows, columns) if the dimension order has been set as *last*.
If the image was initialized with dimension order *last*, the result will be reshaped to *last* (rows, columns, bands) when calling ``img.arr``.

Altering the array replaces all bands. If it is intended to alter a particular band, the remaining bands should be copied.

STAC API Item IO Concept
________________________
To enable reading from different types of file systems (similar to `PySTAC <https://pystac.readthedocs.io/en/latest/concepts.html#using-stac-io>`__), it is recommended that in the ``__init__.py`` of the client module, or at the beginning of the script using ``ukis_pysat.data``, you overwrite the ``StacApiIo.ITEM_URL_IO`` with function that read and write however you need. The following is an example for a on premise S3 environment:
.. code-block:: python

   from ukis_pysat.data import ITEM_URL_IO
   from pystac import Item

    def on_premise_s3_url_method(feature, root_bucket="dem"):
        """the href is build like /collections/*collection_prefix*/items/*item_prefix*

        At some environments we will need to give back the href according to this method.
        """
        item = Item.from_dict(feature)
        href = item.get_self_href()
        stripped_href = href.replace(r"collections/", "").replace(r"items/", "")

        return Item.from_file(f"s3://{root_bucket}{stripped_href}/{item.id}.json")

    ITEM_URL_IO = on_premise_s3_url_method

Environment variables
---------------------
To use ``ukis_pysat.data`` and to download from the respective Datahub you need to set the credentials as environment variables.

For EarthExplorer that's:
 | ``EARTHEXPLORER_USER=your_username``
 | ``EARTHEXPLORER_PW=your_password``

For SciHub that's:
 | ``SCIHUB_USER=your_username``
 | ``SCIHUB_PW=your_password``


.. toctree::
   :caption: Contents:
   :maxdepth: 2

   installation
   api/index

.. toctree::
   :hidden:

   changelog
   about


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
