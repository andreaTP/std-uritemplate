// GENERATED FILE - DO NOT EDIT.
// Source: std-uritemplate.spec.md (sha256 b17b38a95ccb)
// Regenerate: python3 spec/specc.py build --target java
package io.github.stduritemplate;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

public class StdUriTemplate {

    // spec: fn expand
    public static String expand(final String template, final Map<String, Object> substitutions) {
        return expandImpl(template, substitutions);
    }

    // spec: type Operator
    private enum Operator {
        NO_OP,
        PLUS,
        HASH,
        DOT,
        SLASH,
        SEMICOLON,
        QUESTION_MARK,
        AMP;
    }

    // spec: type SubstitutionType
    private enum SubstitutionType {
        EMPTY,
        STRING,
        LIST,
        MAP;
    }

    // spec: fn expandImpl
    private static String expandImpl(String template, Map<String, Object> substitutions) {
        final StringBuilder result = new StringBuilder(template.length() * 2);
        StringBuilder token = null;
        Operator operator = null;
        boolean composite = false;
        StringBuilder maxCharBuffer = null;
        boolean firstToken = true;

        int i = 0;
        while (i < template.length()) {
            int c = template.codePointAt(i);
            if (c == '{') {
                if (token != null) {
                    throw new IllegalArgumentException("Nested expression at col:" + i);
                }
                token = new StringBuilder();
                firstToken = true;
            } else if (c == '}') {
                if (token == null) {
                    throw new IllegalArgumentException("Unexpected '}' at col:" + i);
                }
                if (maxCharBuffer != null && maxCharBuffer.length() == 0) {
                    throw new IllegalArgumentException("Empty prefix modifier at col:" + i);
                }
                boolean expanded = expandToken(operator, token.toString(), composite, getMaxChar(maxCharBuffer, i), firstToken, substitutions, result, i);
                if (expanded && firstToken) {
                    firstToken = false;
                }
                token = null;
                operator = null;
                composite = false;
                maxCharBuffer = null;
            } else if (c == ',' && token != null) {
                if (maxCharBuffer != null && maxCharBuffer.length() == 0) {
                    throw new IllegalArgumentException("Empty prefix modifier at col:" + i);
                }
                boolean expanded = expandToken(operator, token.toString(), composite, getMaxChar(maxCharBuffer, i), firstToken, substitutions, result, i);
                if (expanded && firstToken) {
                    firstToken = false;
                }
                token = new StringBuilder();
                composite = false;
                maxCharBuffer = null;
            } else if (token != null) {
                if (operator == null) {
                    operator = getOperator(c, token, i);
                } else if (maxCharBuffer != null) {
                    if (c >= '0' && c <= '9') {
                        maxCharBuffer.appendCodePoint(c);
                    } else {
                        throw new IllegalArgumentException("Illegal character in prefix modifier at col:" + i);
                    }
                } else if (c == ':') {
                    maxCharBuffer = new StringBuilder();
                } else if (c == '*') {
                    composite = true;
                } else {
                    validateVarchar(c, i);
                    token.appendCodePoint(c);
                }
            } else {
                if (c > 0x7F) {
                    pctEncode(c, result);
                } else {
                    result.appendCodePoint(c);
                }
            }
            i += Character.charCount(c);
        }

        if (token != null) {
            throw new IllegalArgumentException("Unterminated expression");
        }
        return result.toString();
    }

    // spec: fn getOperator
    private static Operator getOperator(int c, StringBuilder token, int col) {
        switch (c) {
            case '+': return Operator.PLUS;
            case '#': return Operator.HASH;
            case '.': return Operator.DOT;
            case '/': return Operator.SLASH;
            case ';': return Operator.SEMICOLON;
            case '?': return Operator.QUESTION_MARK;
            case '&': return Operator.AMP;
            default:
                validateVarchar(c, col);
                token.appendCodePoint(c);
                return Operator.NO_OP;
        }
    }

    // spec: fn validateVarchar
    private static void validateVarchar(int c, int col) {
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
                || c == '_' || c == '%' || c == '.') {
            return;
        }
        throw new IllegalArgumentException("Illegal character in variable name at col:" + col);
    }

    // spec: fn checkVarname
    private static void checkVarname(String token, int col) {
        if (token.startsWith(".") || token.endsWith(".")) {
            throw new IllegalArgumentException("Variable name cannot start or end with a dot at col:" + col);
        }
        if (token.contains("..")) {
            throw new IllegalArgumentException("Variable name cannot contain consecutive dots at col:" + col);
        }
        int i = 0;
        while (i < token.length()) {
            if (token.charAt(i) == '%') {
                if (i + 2 >= token.length()
                        || !isHexDigit(token.charAt(i + 1))
                        || !isHexDigit(token.charAt(i + 2))) {
                    throw new IllegalArgumentException("Invalid percent-encoding in variable name at col:" + col);
                }
                i = i + 3;
            } else {
                i = i + 1;
            }
        }
    }

    // spec: fn isHexDigit
    private static boolean isHexDigit(int c) {
        return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') || (c >= 'a' && c <= 'f');
    }

    // spec: fn getMaxChar
    private static int getMaxChar(StringBuilder buffer, int col) {
        if (buffer == null || buffer.length() == 0) {
            return -1;
        }
        String value = buffer.toString();
        if (value.charAt(0) == '0') {
            throw new IllegalArgumentException("Leading zero not allowed in prefix modifier at col:" + col);
        }
        int n = Integer.parseInt(value);
        if (n < 1 || n > 9999) {
            throw new IllegalArgumentException("Prefix modifier out of range (1-9999) at col:" + col);
        }
        return n;
    }

    // spec: fn expandToken
    private static boolean expandToken(
            Operator operator,
            String token,
            boolean composite,
            int maxChar,
            boolean firstToken,
            Map<String, Object> substitutions,
            StringBuilder result,
            int col) {
        if (token.isEmpty()) {
            throw new IllegalArgumentException("Empty variable name at col:" + col);
        }

        checkVarname(token, col);

        Object value = substitutions.get(token);
        SubstitutionType substType = getSubstitutionType(value, col);
        if (substType == SubstitutionType.EMPTY || isEmpty(substType, value)) {
            return false;
        }

        if (firstToken) {
            addPrefix(operator, result);
        } else {
            addSeparator(operator, result);
        }

        switch (substType) {
            case STRING:
                addStringValue(operator, token, (Object)value, result, maxChar);
                break;
            case LIST:
                addListValue(operator, token, (List<Object>)value, result, maxChar, composite);
                break;
            case MAP:
                addMapValue(operator, token, (Map<String, Object>)value, result, maxChar, composite);
                break;
        }

        return true;
    }

    // spec: fn getSubstitutionType
    private static SubstitutionType getSubstitutionType(Object value, int col) {
        if (value == null) {
            return SubstitutionType.EMPTY;
        } else if (isNativeType(value)) {
            return SubstitutionType.STRING;
        } else if (isList(value)) {
            return SubstitutionType.LIST;
        } else if (isMap(value)) {
            return SubstitutionType.MAP;
        } else {
            throw new IllegalArgumentException("Illegal value type for substitution at col:" + col);
        }
    }

    // spec: fn isEmpty
    private static boolean isEmpty(SubstitutionType substType, Object value) {
        if (value == null) {
            return true;
        } else {
            switch (substType) {
                case STRING: return false;
                case LIST: return ((List)value).isEmpty();
                case MAP: return ((Map)value).isEmpty();
                default: return true;
            }
        }
    }

    // spec: fn isNativeType
    private static boolean isNativeType(Object value) {
        if (value instanceof String ||
            value instanceof Boolean ||
            value instanceof Integer ||
            value instanceof Long ||
            value instanceof Float ||
            value instanceof Double) {
            return true;
        }
        return false;
    }

    // spec: fn isList
    private static boolean isList(Object value) {
        return value instanceof List;
    }

    // spec: fn isMap
    private static boolean isMap(Object value) {
        return value instanceof Map;
    }

    // spec: fn convertNativeTypes
    private static String convertNativeTypes(Object value) {
        if (value instanceof String) {
            return (String)value;
        } else if (value instanceof Boolean) {
            return ((Boolean)value) ? "true" : "false";
        } else if (value instanceof Integer ||
            value instanceof Long ||
            value instanceof Float ||
            value instanceof Double) {
            return value.toString();
        }
        throw new IllegalArgumentException("Illegal value type for substitution");
    }

    // spec: fn addPrefix
    private static void addPrefix(Operator op, StringBuilder result) {
        switch (op) {
            case HASH:
                result.append('#');
                break;
            case DOT:
                result.append('.');
                break;
            case SLASH:
                result.append('/');
                break;
            case SEMICOLON:
                result.append(';');
                break;
            case QUESTION_MARK:
                result.append('?');
                break;
            case AMP:
                result.append('&');
                break;
            default:
                return;
        }
    }

    // spec: fn addSeparator
    private static void addSeparator(Operator op, StringBuilder result) {
        switch (op) {
            case DOT:
                result.append('.');
                break;
            case SLASH:
                result.append('/');
                break;
            case SEMICOLON:
                result.append(';');
                break;
            case QUESTION_MARK:
            case AMP:
                result.append('&');
                break;
            default:
                result.append(',');
                return;
        }
    }

    // spec: fn addStringValue
    private static void addStringValue(Operator operator, String token, Object value, StringBuilder result, int maxChar) {
        addValue(operator, token, value, result, maxChar);
    }

    // spec: fn addListValue
    private static void addListValue(Operator operator, String token, List<Object> value, StringBuilder result, int maxChar, boolean composite) {
        boolean first = true;
        for (Object v: value) {
            if (first) {
                addValue(operator, token, v, result, maxChar);
                first = false;
            } else if (composite) {
                addSeparator(operator, result);
                addValue(operator, token, v, result, maxChar);
            } else {
                result.append(',');
                addValueElement(operator, token, v, result, maxChar);
            }
        }
    }

    // spec: fn addMapValue
    private static void addMapValue(Operator operator, String token, Map<String, Object> value, StringBuilder result, int maxChar, boolean composite) {
        if (maxChar != -1) {
            throw new IllegalArgumentException("Prefix modifier is not allowed on map values");
        }
        boolean first = true;
        for (Map.Entry<String, Object> v : value.entrySet()) {
            if (composite) {
                if (!first) {
                    addSeparator(operator, result);
                }
                addValueElement(operator, token, v.getKey(), result, maxChar);
                result.append('=');
            } else {
                if (first) {
                    addValue(operator, token, v.getKey(), result, maxChar);
                } else {
                    result.append(',');
                    addValueElement(operator, token, v.getKey(), result, maxChar);
                }
                result.append(',');
            }
            addValueElement(operator, token, v.getValue(), result, maxChar);
            first = false;
        }
    }

    // spec: fn addValue
    private static void addValue(Operator op, String token, Object value, StringBuilder result, int maxChar) {
        switch (op) {
            case PLUS:
            case HASH:
                addExpandedValue(null, value, result, maxChar, false);
                break;
            case QUESTION_MARK:
            case AMP:
                result.append(token + '=');
                addExpandedValue(null, value, result, maxChar, true);
                break;
            case SEMICOLON:
                result.append(token);
                addExpandedValue("=", value, result, maxChar, true);
                break;
            case DOT:
            case SLASH:
            case NO_OP:
                addExpandedValue(null, value, result, maxChar, true);
        }
    }

    // spec: fn addValueElement
    private static void addValueElement(Operator op, String token, Object value, StringBuilder result, int maxChar) {
        switch (op) {
            case PLUS:
            case HASH:
                addExpandedValue(null, value, result, maxChar, false);
                break;
            case QUESTION_MARK:
            case AMP:
            case SEMICOLON:
            case DOT:
            case SLASH:
            case NO_OP:
                addExpandedValue(null, value, result, maxChar, true);
        }
    }

    // spec: fn addExpandedValue
    private static void addExpandedValue(String prefix, Object value, StringBuilder result, int maxChar, boolean replaceReserved) {
        int[] s = convertNativeTypes(value).codePoints().toArray();
        int max = (maxChar == -1) ? s.length : Math.min(maxChar, s.length);

        if (max > 0 && prefix != null) {
            result.append(prefix);
        }

        int i = 0;
        while (i < max) {
            int c = s[i];
            if (isUnreserved(c)) {
                result.appendCodePoint(c);
            } else if (!replaceReserved && isReserved(c)) {
                result.appendCodePoint(c);
            } else if (!replaceReserved && c == '%' && i + 2 < max && isHexDigit(s[i + 1]) && isHexDigit(s[i + 2])) {
                result.appendCodePoint(c);
                result.appendCodePoint(s[i + 1]);
                result.appendCodePoint(s[i + 2]);
                i = i + 2;
            } else {
                pctEncode(c, result);
            }
            i = i + 1;
        }
    }

    // spec: fn isUnreserved
    private static boolean isUnreserved(int c) {
        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
                || c == '-' || c == '.' || c == '_' || c == '~';
    }

    // spec: fn isReserved
    private static boolean isReserved(int c) {
        return ":/?#[]@!$&'()*+,;=".indexOf(c) >= 0;
    }

    // spec: fn pctEncode
    private static void pctEncode(int c, StringBuilder result) {
        for (byte b : new String(Character.toChars(c)).getBytes(StandardCharsets.UTF_8)) {
            result.append(String.format("%%%02X", b & 0xFF));
        }
    }

}
