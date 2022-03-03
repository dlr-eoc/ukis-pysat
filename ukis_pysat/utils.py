import pystac
from geojson import Feature
from pystac import ProviderRole
from pystac.extensions.sar import FrequencyBand, SarExtension, Polarization


def fill_sar_ext(sar_ext: SarExtension, meta: Feature):
    # Fixed properties
    sar_ext.frequency_band = FrequencyBand("C")
    sar_ext.center_frequency = 5.405
    # rest (like e.g. sar:pixel_spacing_range) cannot be known from API response AFAIK

    # Read properties
    sar_ext.instrument_mode = meta["properties"]["sensoroperationalmode"]
    sar_ext.product_type = meta["properties"]["producttype"]

    # TODO maybe this is not good, because we often only use one later on
    sar_ext.polarizations = [Polarization(p) for p in meta["properties"]["polarisationmode"].split(" ")]


# constants
SENTINEL_PROVIDER = pystac.Provider(
    name="ESA",
    roles=[
        ProviderRole.PRODUCER,
        ProviderRole.PROCESSOR,
        ProviderRole.LICENSOR,
    ],
    url="https://earth.esa.int/web/guest/home",
)
