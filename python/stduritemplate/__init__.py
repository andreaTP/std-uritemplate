# GENERATED FILE - DO NOT EDIT.
# Source: std-uritemplate.spec.md (sha256 e425ac90abca)
# Regenerate: python3 spec/specc.py build --target python
from typing import Any, Dict, List, Optional
from enum import Enum


# spec: type Operator
class _Operator(Enum):
    PLUS = "+"
    HASH = "#"
    DOT = "."
    SLASH = "/"
    SEMICOLON = ";"
    QUESTION_MARK = "?"
    AMP = "&"
    NO_OP = ""


# spec: type SubstitutionType
class _SubstitutionType(Enum):
    EMPTY = 0
    STRING = 1
    LIST = 2
    MAP = 3


class StdUriTemplate:
    # spec: fn expand
    @staticmethod
    def expand(template: str, substitutions: Dict[str, Any]) -> str:
        return StdUriTemplate.__expand_impl(template, substitutions)

    # spec: fn expandImpl
    @staticmethod
    def __expand_impl(template: str, substitutions: Dict[str, Any]) -> str:
        result = []
        token = None
        operator = None
        composite = False
        max_char_buffer = None
        first_token = True

        for i in range(len(template)):
            character = template[i]
            if character == "{":
                if token is not None:
                    raise ValueError(f"Nested expression at col:{i}")
                token = []
                first_token = True
            elif character == "}":
                if token is None:
                    raise ValueError(f"Unexpected '}}' at col:{i}")
                if max_char_buffer is not None and len(max_char_buffer) == 0:
                    raise ValueError(f"Empty prefix modifier at col:{i}")
                expanded = StdUriTemplate.__expand_token(
                    operator,
                    "".join(token),
                    composite,
                    StdUriTemplate.__get_max_char(max_char_buffer, i),
                    first_token,
                    substitutions,
                    result,
                    i,
                )
                if expanded and first_token:
                    first_token = False
                token = None
                operator = None
                composite = False
                max_char_buffer = None
            elif character == "," and token is not None:
                if max_char_buffer is not None and len(max_char_buffer) == 0:
                    raise ValueError(f"Empty prefix modifier at col:{i}")
                expanded = StdUriTemplate.__expand_token(
                    operator,
                    "".join(token),
                    composite,
                    StdUriTemplate.__get_max_char(max_char_buffer, i),
                    first_token,
                    substitutions,
                    result,
                    i,
                )
                if expanded and first_token:
                    first_token = False
                token = []
                composite = False
                max_char_buffer = None
            elif token is not None:
                if operator is None:
                    operator = StdUriTemplate.__get_operator(character, token, i)
                elif max_char_buffer is not None:
                    if "0" <= character <= "9":
                        max_char_buffer.append(character)
                    else:
                        raise ValueError(
                            f"Illegal character in prefix modifier at col:{i}"
                        )
                elif character == ":":
                    max_char_buffer = []
                elif character == "*":
                    composite = True
                else:
                    StdUriTemplate.__validate_varchar(character, i)
                    token.append(character)
            else:
                if ord(character) > 0x7F:
                    StdUriTemplate.__pct_encode(character, result)
                else:
                    result.append(character)

        if token is not None:
            raise ValueError("Unterminated expression")
        return "".join(result)

    # spec: fn getOperator
    @staticmethod
    def __get_operator(character: str, token: List[str], col: int) -> _Operator:
        if character == "+":
            return _Operator.PLUS
        if character == "#":
            return _Operator.HASH
        if character == ".":
            return _Operator.DOT
        if character == "/":
            return _Operator.SLASH
        if character == ";":
            return _Operator.SEMICOLON
        if character == "?":
            return _Operator.QUESTION_MARK
        if character == "&":
            return _Operator.AMP
        StdUriTemplate.__validate_varchar(character, col)
        token.append(character)
        return _Operator.NO_OP

    # spec: fn validateVarchar
    @staticmethod
    def __validate_varchar(c: str, col: int) -> None:
        if (
            ("a" <= c <= "z")
            or ("A" <= c <= "Z")
            or ("0" <= c <= "9")
            or c == "_"
            or c == "%"
            or c == "."
        ):
            return
        raise ValueError(f"Illegal character in variable name at col:{col}")

    # spec: fn checkVarname
    @staticmethod
    def __check_varname(token: str, col: int) -> None:
        if token.startswith(".") or token.endswith("."):
            raise ValueError(f"Variable name cannot start or end with a dot at col:{col}")
        if ".." in token:
            raise ValueError(f"Variable name cannot contain consecutive dots at col:{col}")
        i = 0
        while i < len(token):
            if token[i] == "%":
                if (
                    i + 2 >= len(token)
                    or not StdUriTemplate.__is_hex_digit(token[i + 1])
                    or not StdUriTemplate.__is_hex_digit(token[i + 2])
                ):
                    raise ValueError(
                        f"Invalid percent-encoding in variable name at col:{col}"
                    )
                i = i + 3
            else:
                i = i + 1

    # spec: fn isHexDigit
    @staticmethod
    def __is_hex_digit(c: str) -> bool:
        return ("0" <= c <= "9") or ("A" <= c <= "F") or ("a" <= c <= "f")

    # spec: fn getMaxChar
    @staticmethod
    def __get_max_char(buffer: Optional[List[str]], col: int) -> int:
        if buffer is None or len(buffer) == 0:
            return -1
        value = "".join(buffer)
        if value[0] == "0":
            raise ValueError(f"Leading zero not allowed in prefix modifier at col:{col}")
        n = int(value)
        if n < 1 or n > 9999:
            raise ValueError(f"Prefix modifier out of range (1-9999) at col:{col}")
        return n

    # spec: fn expandToken
    @staticmethod
    def __expand_token(
        operator: _Operator,
        token: str,
        composite: bool,
        max_char: int,
        first_token: bool,
        substitutions: Dict[str, Any],
        result: List[str],
        col: int,
    ) -> bool:
        if len(token) == 0:
            raise ValueError(f"Empty variable name at col:{col}")
        StdUriTemplate.__check_varname(token, col)
        value = substitutions.get(token)
        subst_type = StdUriTemplate.__get_substitution_type(value, col)
        if subst_type == _SubstitutionType.EMPTY or StdUriTemplate.__is_empty(
            subst_type, value
        ):
            return False
        if first_token:
            StdUriTemplate.__add_prefix(operator, result)
        else:
            StdUriTemplate.__add_separator(operator, result)
        if subst_type == _SubstitutionType.STRING:
            StdUriTemplate.__add_string_value(operator, token, value, result, max_char)
        elif subst_type == _SubstitutionType.LIST:
            StdUriTemplate.__add_list_value(
                operator, token, value, result, max_char, composite
            )
        elif subst_type == _SubstitutionType.MAP:
            StdUriTemplate.__add_map_value(
                operator, token, value, result, max_char, composite
            )
        return True

    # spec: fn getSubstitutionType
    @staticmethod
    def __get_substitution_type(value: Any, col: int) -> _SubstitutionType:
        if value is None:
            return _SubstitutionType.EMPTY
        if StdUriTemplate.__is_native_type(value):
            return _SubstitutionType.STRING
        if StdUriTemplate.__is_list(value):
            return _SubstitutionType.LIST
        if StdUriTemplate.__is_map(value):
            return _SubstitutionType.MAP
        raise ValueError(f"Illegal value type for substitution at col:{col}")

    # spec: fn isEmpty
    @staticmethod
    def __is_empty(subst_type: _SubstitutionType, value: Any) -> bool:
        if value is None:
            return True
        if subst_type == _SubstitutionType.STRING:
            return False
        if subst_type == _SubstitutionType.LIST:
            return len(value) == 0
        if subst_type == _SubstitutionType.MAP:
            return len(value) == 0
        return True

    # spec: fn isNativeType
    @staticmethod
    def __is_native_type(value: Any) -> bool:
        return isinstance(value, (str, bool, int, float))

    # spec: fn isList
    @staticmethod
    def __is_list(value: Any) -> bool:
        return isinstance(value, list)

    # spec: fn isMap
    @staticmethod
    def __is_map(value: Any) -> bool:
        return isinstance(value, dict)

    # spec: fn convertNativeTypes
    @staticmethod
    def __convert_native_types(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        raise ValueError("Illegal value type for substitution")

    # spec: fn addPrefix
    @staticmethod
    def __add_prefix(op: _Operator, result: List[str]) -> None:
        if op == _Operator.HASH:
            result.append("#")
        elif op == _Operator.DOT:
            result.append(".")
        elif op == _Operator.SLASH:
            result.append("/")
        elif op == _Operator.SEMICOLON:
            result.append(";")
        elif op == _Operator.QUESTION_MARK:
            result.append("?")
        elif op == _Operator.AMP:
            result.append("&")

    # spec: fn addSeparator
    @staticmethod
    def __add_separator(op: _Operator, result: List[str]) -> None:
        if op == _Operator.DOT:
            result.append(".")
        elif op == _Operator.SLASH:
            result.append("/")
        elif op == _Operator.SEMICOLON:
            result.append(";")
        elif op == _Operator.QUESTION_MARK or op == _Operator.AMP:
            result.append("&")
        else:
            result.append(",")

    # spec: fn addStringValue
    @staticmethod
    def __add_string_value(
        op: _Operator, token: str, value: Any, result: List[str], max_char: int
    ) -> None:
        StdUriTemplate.__add_value(op, token, value, result, max_char)

    # spec: fn addListValue
    @staticmethod
    def __add_list_value(
        op: _Operator,
        token: str,
        value: List[Any],
        result: List[str],
        max_char: int,
        composite: bool,
    ) -> None:
        first = True
        for v in value:
            if first:
                StdUriTemplate.__add_value(op, token, v, result, max_char)
                first = False
            elif composite:
                StdUriTemplate.__add_separator(op, result)
                StdUriTemplate.__add_value(op, token, v, result, max_char)
            else:
                result.append(",")
                StdUriTemplate.__add_value_element(op, token, v, result, max_char)

    # spec: fn addMapValue
    @staticmethod
    def __add_map_value(
        op: _Operator,
        token: str,
        value: Dict[str, Any],
        result: List[str],
        max_char: int,
        composite: bool,
    ) -> None:
        if max_char != -1:
            raise ValueError("Prefix modifier is not allowed on map values")
        first = True
        for k, v in value.items():
            if composite:
                if not first:
                    StdUriTemplate.__add_separator(op, result)
                StdUriTemplate.__add_value_element(op, token, k, result, max_char)
                result.append("=")
            else:
                if first:
                    StdUriTemplate.__add_value(op, token, k, result, max_char)
                else:
                    result.append(",")
                    StdUriTemplate.__add_value_element(op, token, k, result, max_char)
                result.append(",")
            StdUriTemplate.__add_value_element(op, token, v, result, max_char)
            first = False

    # spec: fn addValue
    @staticmethod
    def __add_value(
        op: _Operator, token: str, value: Any, result: List[str], max_char: int
    ) -> None:
        if op == _Operator.PLUS or op == _Operator.HASH:
            StdUriTemplate.__add_expanded_value(None, value, result, max_char, False)
        elif op == _Operator.QUESTION_MARK or op == _Operator.AMP:
            result.append(token)
            result.append("=")
            StdUriTemplate.__add_expanded_value(None, value, result, max_char, True)
        elif op == _Operator.SEMICOLON:
            result.append(token)
            StdUriTemplate.__add_expanded_value("=", value, result, max_char, True)
        else:
            StdUriTemplate.__add_expanded_value(None, value, result, max_char, True)

    # spec: fn addValueElement
    @staticmethod
    def __add_value_element(
        op: _Operator, token: str, value: Any, result: List[str], max_char: int
    ) -> None:
        if op == _Operator.PLUS or op == _Operator.HASH:
            StdUriTemplate.__add_expanded_value(None, value, result, max_char, False)
        else:
            StdUriTemplate.__add_expanded_value(None, value, result, max_char, True)

    # spec: fn addExpandedValue
    @staticmethod
    def __add_expanded_value(
        prefix: Optional[str],
        value: Any,
        result: List[str],
        max_char: int,
        replace_reserved: bool,
    ) -> None:
        s = StdUriTemplate.__convert_native_types(value)
        max_val = len(s) if max_char == -1 else min(max_char, len(s))
        if max_val > 0 and prefix is not None:
            result.append(prefix)
        i = 0
        while i < max_val:
            c = s[i]
            if StdUriTemplate.__is_unreserved(c):
                result.append(c)
            elif not replace_reserved and StdUriTemplate.__is_reserved(c):
                result.append(c)
            elif (
                not replace_reserved
                and c == "%"
                and i + 2 < max_val
                and StdUriTemplate.__is_hex_digit(s[i + 1])
                and StdUriTemplate.__is_hex_digit(s[i + 2])
            ):
                result.append(c)
                result.append(s[i + 1])
                result.append(s[i + 2])
                i = i + 2
            else:
                StdUriTemplate.__pct_encode(c, result)
            i = i + 1

    # spec: fn isUnreserved
    @staticmethod
    def __is_unreserved(c: str) -> bool:
        return (
            ("a" <= c <= "z")
            or ("A" <= c <= "Z")
            or ("0" <= c <= "9")
            or c == "-"
            or c == "."
            or c == "_"
            or c == "~"
        )

    # spec: fn isReserved
    @staticmethod
    def __is_reserved(c: str) -> bool:
        return c in ":/?#[]@!$&'()*+,;="

    # spec: fn pctEncode
    @staticmethod
    def __pct_encode(c: str, result: List[str]) -> None:
        for b in c.encode("utf-8"):
            result.append("%{:02X}".format(b))
