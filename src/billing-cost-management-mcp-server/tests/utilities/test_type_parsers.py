"""Tests for type parsing utilities."""

import pytest
from awslabs.billing_cost_management_mcp_server.utilities.type_parsers import (
    parse_complex_param,
    parse_int_param,
    parse_float_param
)


class TestParseComplexParam:
    """Tests for parse_complex_param()"""

    def test_dict_input(self):
        """Should return dict as-is"""
        result = parse_complex_param(
            {"key": "value"},
            "test_func",
            "param"
        )
        assert result == {"key": "value"}

    def test_json_string_input(self):
        """Should parse JSON string"""
        result = parse_complex_param(
            '{"key": "value"}',
            "test_func",
            "param"
        )
        assert result == {"key": "value"}

    def test_none_input(self):
        """Should return None"""
        result = parse_complex_param(None, "test_func", "param")
        assert result is None

    def test_empty_string_input(self):
        """Should return None for empty string"""
        result = parse_complex_param("", "test_func", "param")
        assert result is None

    def test_invalid_json(self):
        """Should raise ValueError for invalid JSON"""
        with pytest.raises(ValueError, match="Invalid JSON format"):
            parse_complex_param("invalid json", "test_func", "param")

    def test_list_input(self):
        """Should return list as-is"""
        result = parse_complex_param(
            [{"key": "value"}],
            "test_func",
            "param"
        )
        assert result == [{"key": "value"}]

    def test_json_array_string(self):
        """Should parse JSON array string"""
        result = parse_complex_param(
            '[{"key": "value"}]',
            "test_func",
            "param"
        )
        assert result == [{"key": "value"}]

    def test_complex_nested_object(self):
        """Should handle complex nested objects"""
        complex_obj = {
            "Dimensions": {
                "Key": "SERVICE",
                "Values": ["EC2", "S3"]
            }
        }
        result = parse_complex_param(complex_obj, "test_func", "filter")
        assert result == complex_obj

    def test_invalid_type(self):
        """Should raise ValueError for invalid type"""
        with pytest.raises(ValueError, match="must be string, dict, or list"):
            parse_complex_param(12345, "test_func", "param")


class TestParseIntParam:
    """Tests for parse_int_param()"""

    def test_int_input(self):
        """Should return int as-is"""
        result = parse_int_param(50, "test_func", "param")
        assert result == 50

    def test_string_input(self):
        """Should parse string to int"""
        result = parse_int_param("50", "test_func", "param")
        assert result == 50

    def test_none_input(self):
        """Should return None"""
        result = parse_int_param(None, "test_func", "param")
        assert result is None

    def test_none_with_default(self):
        """Should return default value"""
        result = parse_int_param(None, "test_func", "param", default=100)
        assert result == 100

    def test_invalid_string(self):
        """Should raise ValueError for invalid string"""
        with pytest.raises(ValueError, match="Invalid integer format"):
            parse_int_param("invalid", "test_func", "param")

    def test_float_string(self):
        """Should raise ValueError for float string"""
        with pytest.raises(ValueError, match="Invalid integer format"):
            parse_int_param("3.14", "test_func", "param")

    def test_min_value_validation(self):
        """Should enforce minimum value"""
        with pytest.raises(ValueError, match="must be >= 1"):
            parse_int_param(0, "test_func", "param", min_value=1)

    def test_max_value_validation(self):
        """Should enforce maximum value"""
        with pytest.raises(ValueError, match="must be <= 100"):
            parse_int_param(101, "test_func", "param", max_value=100)

    def test_range_validation_pass(self):
        """Should pass range validation"""
        result = parse_int_param(
            50,
            "test_func",
            "param",
            min_value=1,
            max_value=100
        )
        assert result == 50

    def test_negative_int(self):
        """Should handle negative integers"""
        result = parse_int_param(-10, "test_func", "param")
        assert result == -10

    def test_zero(self):
        """Should handle zero"""
        result = parse_int_param(0, "test_func", "param")
        assert result == 0

    def test_large_int(self):
        """Should handle large integers"""
        result = parse_int_param(999999, "test_func", "param")
        assert result == 999999

    def test_string_with_leading_zeros(self):
        """Should parse string with leading zeros"""
        result = parse_int_param("007", "test_func", "param")
        assert result == 7

    def test_invalid_type(self):
        """Should raise ValueError for invalid type"""
        with pytest.raises(ValueError, match="must be string or int"):
            parse_int_param(3.14, "test_func", "param")


class TestParseFloatParam:
    """Tests for parse_float_param()"""

    def test_float_input(self):
        """Should return float as-is"""
        result = parse_float_param(3.14, "test_func", "param")
        assert result == 3.14

    def test_int_input(self):
        """Should convert int to float"""
        result = parse_float_param(50, "test_func", "param")
        assert result == 50.0

    def test_string_input(self):
        """Should parse string to float"""
        result = parse_float_param("3.14", "test_func", "param")
        assert result == 3.14

    def test_int_string_input(self):
        """Should parse int string to float"""
        result = parse_float_param("50", "test_func", "param")
        assert result == 50.0

    def test_none_input(self):
        """Should return None"""
        result = parse_float_param(None, "test_func", "param")
        assert result is None

    def test_none_with_default(self):
        """Should return default value"""
        result = parse_float_param(None, "test_func", "param", default=30.0)
        assert result == 30.0

    def test_invalid_string(self):
        """Should raise ValueError for invalid string"""
        with pytest.raises(ValueError, match="Invalid float format"):
            parse_float_param("invalid", "test_func", "param")

    def test_min_value_validation(self):
        """Should enforce minimum value"""
        with pytest.raises(ValueError, match="must be >= 0.1"):
            parse_float_param(0.05, "test_func", "param", min_value=0.1)

    def test_max_value_validation(self):
        """Should enforce maximum value"""
        with pytest.raises(ValueError, match="must be <= 100.0"):
            parse_float_param(101.5, "test_func", "param", max_value=100.0)

    def test_range_validation_pass(self):
        """Should pass range validation"""
        result = parse_float_param(
            50.5,
            "test_func",
            "param",
            min_value=0.1,
            max_value=100.0
        )
        assert result == 50.5

    def test_negative_float(self):
        """Should handle negative floats"""
        result = parse_float_param(-3.14, "test_func", "param")
        assert result == -3.14

    def test_zero_float(self):
        """Should handle zero"""
        result = parse_float_param(0.0, "test_func", "param")
        assert result == 0.0

    def test_scientific_notation_string(self):
        """Should parse scientific notation"""
        result = parse_float_param("1.5e2", "test_func", "param")
        assert result == 150.0

    def test_invalid_type(self):
        """Should raise ValueError for invalid type"""
        with pytest.raises(ValueError, match="must be string, float, or int"):
            parse_float_param([], "test_func", "param")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
