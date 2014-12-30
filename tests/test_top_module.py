import wasp


def test_version():
    old_version = wasp.version

    wasp.version = wasp.WaspVersion(1, 0, 0)
    try:
        wasp.require_version(1, 1)
        compatible = True
    except AssertionError:
        compatible = False
    assert not compatible, 'Version should be incompatible'

    wasp.version = wasp.WaspVersion(1, 1, 0)
    try:
        wasp.require_version(1, 0, 3)
        compatible = True
    except AssertionError:
        compatible = False
    assert not compatible, 'Version should be compatible'

    wasp.version = wasp.WaspVersion(1, 3, 2)
    try:
        wasp.require_version(1, 2)
        compatible = True
    except AssertionError:
        compatible = False
    assert compatible, 'Version should be compatible'

    wasp.version = wasp.WaspVersion(1, 3, 2)
    try:
        wasp.require_version(1)
        compatible = True
    except AssertionError:
        compatible = False
    assert compatible, 'Version should be compatible'

    wasp.version = old_version
