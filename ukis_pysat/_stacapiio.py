from pystac import Item


class StacApiIo:
    def default_build_url_method(feature):
        return Item.from_dict(feature)

    def on_premise_s3_url_method(feature, root_bucket="dem"):
        """the href is build like /collections/*collection_prefix*/items/*item_prefix*

        At some environments at DLR we will need to give back the href according to this method.
        """
        item = Item.from_dict(feature)
        href = item.get_self_href()
        stripped_href = href.replace(r"collections/", "").replace(r"items/", "")

        return Item.from_file(f"s3://{root_bucket}{stripped_href}/{item.id}.json")

    url_method = default_build_url_method
    """Like in PySTAC you can replace the parse_url_method to expand the ability to read different file systems.
    For example, a client of the library might replace this class  member in it's own __init__.py with a method that 
    can read from another cloud storage.
    """

    @classmethod
    def build_url(cls, feature):
        return cls.url_method(feature)
