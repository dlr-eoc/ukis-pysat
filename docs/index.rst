.. ukis-pysat documentation master file, created by
   sphinx-quickstart on Mon Apr 20 11:21:17 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to UKIS-pysat's documentation!
======================================

The UKIS-pysat package provides generic classes and functions to query, access and process multi-spectral and SAR satellite images.

.. code-block:: python

  from ukis_pysat.file import get_sentinel_scene_from_dir
  from ukis_pysat.download import Source
  from ukis_pysat.data import Image
  from ukis_pysat.members import Datahub

  download_source = Source(source=Datahub.Scihub)
  download_source.download_image(product_srcid, product_uuid, target_dir)

  with get_sentinel_scene_from_dir(target_dir) as (full_path, ident):
      img = Image(os.path.join(full_path, 'pre_nrcs.tif'))


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
