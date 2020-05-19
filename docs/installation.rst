Installation
============

Installation with pip
---------------------

Most users will want to do this:

.. code-block:: console

    pip install ukis-pysat[complete]  # install everything

There's also some lighter versions with less dependencies:

.. code-block:: console

    pip install ukis-pysat  # only install core features (ukis_pysat.file)

    pip install ukis-pysat[data]  # install dependencies for ukis_pysat.file and ukis_pysat.data

    pip install ukis-pysat[raster]  # install dependencies for ukis_pysat.file and ukis_pysat.raster

Installation with Anaconda
--------------------------
You can install pysat using Anaconda using the following commands:

.. code-block:: console

    git clone https://github.com/dlr-eoc/ukis-pysat
    cd ukis-pysat
    conda env create -f environment.yml
    conda activate ukis_pysat


GDAL
----
If you're having troubles installing GDAL and Rasterio follow these `instructions
<https://rasterio.readthedocs.io/en/latest/installation.html>`__.

Tests
-----
To run the tests set the Environment variables and then:

.. code-block:: console

    git clone https://github.com/dlr-eoc/ukis-pysat
    cd ukis-pysat
    conda env create -f environment.yml
    conda activate ukis_pysat
    export
    python -m unittest discover tests

If you set the environment variables with the credentials to the hubs, you can uncomment `@unittest.skip()` for these tests.