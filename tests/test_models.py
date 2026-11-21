import pytest

from nato_symbol_generator.models import InvalidSidcError, Sidc


def test_sidc_fields_preserve_fixed_width() -> None:
    sidc = Sidc("10030100001103000000")
    assert sidc.version == "10"
    assert sidc.context == "0"
    assert sidc.identity == "3"
    assert sidc.symbol_set == "01"
    assert sidc.entity == "110300"
    assert str(sidc) == "10030100001103000000"


@pytest.mark.parametrize("value", ["", "123", "A" * 20, "1" * 21])
def test_invalid_sidc_is_rejected(value: str) -> None:
    with pytest.raises(InvalidSidcError):
        Sidc(value)

