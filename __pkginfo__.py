import typing

numversion: typing.Tuple[int, int, int] = (0, 0, 0)
dev_version: int = 0

version: str = ".".join(str(num) for num in numversion)
if dev_version is not None:
    version += ".dev" + str(dev_version)
