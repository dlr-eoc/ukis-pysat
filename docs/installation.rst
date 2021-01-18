Installation
============

Installation with pip
---------------------

Most users will want to do this:

.. code-block:: console

    pip install ukis-pysat[complete]  # install everything

There's also some lighter versions with less dependencies:

.. code-block:: console

    pip install ukis-pysat  # only install core dependencies (ukis_pysat.file can be used)

    pip install ukis-pysat[data]  # also install dependencies for ukis_pysat.data

    pip install ukis-pysat[raster]  # also install dependencies for ukis_pysat.raster

Some helper functions might need additional dependencies like `pandas`, `dask[array]` or `utm`. If this is the case you will receive an `ImportError`.

GDAL
----
If you're having troubles installing GDAL and Rasterio use conda and/or follow these `instructions
<https://rasterio.readthedocs.io/en/latest/installation.html>`__.

Tests
-----
To run the tests set the Environment variables and then:

.. code-block:: console

    git clone https://github.com/dlr-eoc/ukis-pysat
    cd ukis-pysat
    pip install -e .[dev]
    python -m unittest discover tests

If you set the environment variables with the credentials to the hubs, you can uncomment `@unittest.skip()` for these tests.