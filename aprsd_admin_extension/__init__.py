from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("aprsd-admin-extension")
except PackageNotFoundError:
    pass
