.. ukis-pysat documentation master file, created by
   sphinx-quickstart on Mon Apr 20 11:21:17 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to UKIS-pysat's documentation!
======================================

The UKIS-pysat package provides generic classes and functions to access and process multi-spectral and SAR satellite images.

file
____
Work with you local satellite data files and read information out of file names and metadata files. Currently, focusing on Sentinel-1.

raster
______
Reading satellite data and performing simple, but cumbersome tasks. This is just a layer on top of `rasterio <https://github.com/rasterio/rasterio>`__ for stuff we often need. It can very well be that using *rasterio* directly is often the better choice.

Example
_______
Here's an example about some basic features:

.. code-block:: python

   from ukis_pysat.file import get_sentinel_scene_from_dir
   from ukis_pysat.raster import Image


   # get sentinel scene from directory
   with get_sentinel_scene_from_dir("/users/username/tmp") as (full_path, ident):
       with Image(full_path.join("pre_nrcs.tif")) as img:
           # scale the image array, having one band
           img.arr = img.arr * 0.3

Dimension order
---------------
The dimension order can be set upon initialization and you have to choose between *first* (bands, rows, columns), being raster shape needed for rasterio, or *last* (rows, columns, bands), being image shape used by most image processing libraries. Default is *first*.
Compare with the `documentation of rasterio <https://rasterio.readthedocs.io/en/latest/api/rasterio.plot.html#rasterio.plot.reshape_as_image>`__. UKIS-pysat uses rasterio internally and the dimension order is always reshaped to *first* (bands, rows, columns) if the dimension order has been set as *last*.
If the image was initialized with dimension order *last*, the result will be reshaped to *last* (rows, columns, bands) when calling ``img.arr``.

Altering the array replaces all bands. If it is intended to alter a particular band, the remaining bands should be copied.


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
