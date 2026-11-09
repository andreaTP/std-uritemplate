// GENERATED FILE - DO NOT EDIT.
// Source: std-uritemplate.spec.md (sha256 e425ac90abca)
// Regenerate: python3 spec/specc.py build --target csharp

namespace Std;

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

public class UriTemplate
{
    // Public API
    // spec: fn expand
    public static string Expand(string template, IReadOnlyDictionary<string, object> substitutions)
    {
        return ExpandImpl(template, substitutions);
    }

    // Private implementation
    // spec: type Operator
    private enum Operator
    {
        NO_OP,
        PLUS,
        HASH,
        DOT,
        SLASH,
        SEMICOLON,
        QUESTION_MARK,
        AMP
    }

    // spec: type SubstitutionType
    private enum SubstitutionType
    {
        EMPTY,
        STRING,
        LIST,
        MAP
    }

    // spec: fn expandImpl
    private static string ExpandImpl(string template, IReadOnlyDictionary<string, object> substitutions)
    {
        StringBuilder result = new StringBuilder(template.Length * 2);
        StringBuilder? token = null;
        Operator? op = null;
        bool composite = false;
        StringBuilder? maxCharBuffer = null;
        bool firstToken = true;

        for (int i = 0; i < template.Length; i += char.IsHighSurrogate(template, i) ? 2 : 1)
        {
            int c = char.ConvertToUtf32(template, i);
            if (c == '{')
            {
                if (token != null)
                {
                    throw new ArgumentException($"Nested expression at col:{i}");
                }
                token = new StringBuilder();
                firstToken = true;
            }
            else if (c == '}')
            {
                if (token == null)
                {
                    throw new ArgumentException($"Unexpected '}}' at col:{i}");
                }
                if (maxCharBuffer != null && maxCharBuffer.Length == 0)
                {
                    throw new ArgumentException($"Empty prefix modifier at col:{i}");
                }
                bool expanded = ExpandToken(op, token.ToString(), composite, GetMaxChar(maxCharBuffer, i), firstToken, substitutions, result, i);
                if (expanded && firstToken)
                {
                    firstToken = false;
                }
                token = null;
                op = null;
                composite = false;
                maxCharBuffer = null;
            }
            else if (c == ',' && token != null)
            {
                if (maxCharBuffer != null && maxCharBuffer.Length == 0)
                {
                    throw new ArgumentException($"Empty prefix modifier at col:{i}");
                }
                bool expanded = ExpandToken(op, token.ToString(), composite, GetMaxChar(maxCharBuffer, i), firstToken, substitutions, result, i);
                if (expanded && firstToken)
                {
                    firstToken = false;
                }
                token = new StringBuilder();
                composite = false;
                maxCharBuffer = null;
            }
            else if (token != null)
            {
                if (op == null)
                {
                    op = GetOperator(c, token, i);
                }
                else if (maxCharBuffer != null)
                {
                    if (c >= '0' && c <= '9')
                    {
                        maxCharBuffer.Append(char.ConvertFromUtf32(c));
                    }
                    else
                    {
                        throw new ArgumentException($"Illegal character in prefix modifier at col:{i}");
                    }
                }
                else if (c == ':')
                {
                    maxCharBuffer = new StringBuilder();
                }
                else if (c == '*')
                {
                    composite = true;
                }
                else
                {
                    ValidateVarchar(c, i);
                    token.Append(char.ConvertFromUtf32(c));
                }
            }
            else
            {
                if (c > 0x7F)
                {
                    PctEncode(c, result);
                }
                else
                {
                    result.Append(char.ConvertFromUtf32(c));
                }
            }
        }

        if (token != null)
        {
            throw new ArgumentException("Unterminated expression");
        }
        return result.ToString();
    }

    // spec: fn getOperator
    private static Operator GetOperator(int c, StringBuilder token, int col)
    {
        switch (c)
        {
            case '+': return Operator.PLUS;
            case '#': return Operator.HASH;
            case '.': return Operator.DOT;
            case '/': return Operator.SLASH;
            case ';': return Operator.SEMICOLON;
            case '?': return Operator.QUESTION_MARK;
            case '&': return Operator.AMP;
            default:
                ValidateVarchar(c, col);
                token.Append(char.ConvertFromUtf32(c));
                return Operator.NO_OP;
        }
    }

    // spec: fn validateVarchar
    private static void ValidateVarchar(int c, int col)
    {
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '%' || c == '.')
        {
            return;
        }
        throw new ArgumentException($"Illegal character in variable name at col:{col}");
    }

    // spec: fn checkVarname
    private static void CheckVarname(string token, int col)
    {
#if NETSTANDARD2_1_OR_GREATER || NETCOREAPP2_1_OR_GREATER
        if (token.StartsWith('.') || token.EndsWith('.'))
#else
        if (token.StartsWith(".") || token.EndsWith("."))
#endif
        {
            throw new ArgumentException($"Variable name cannot start or end with a dot at col:{col}");
        }
        if (token.Contains(".."))
        {
            throw new ArgumentException($"Variable name cannot contain consecutive dots at col:{col}");
        }
        int i = 0;
        while (i < token.Length)
        {
            if (token[i] == '%')
            {
                if (i + 2 >= token.Length
                    || !IsHexDigit(token[i + 1])
                    || !IsHexDigit(token[i + 2]))
                {
                    throw new ArgumentException($"Invalid percent-encoding in variable name at col:{col}");
                }
                i += 3;
            }
            else
            {
                i += 1;
            }
        }
    }

    // spec: fn isHexDigit
    private static bool IsHexDigit(int c)
    {
        return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') || (c >= 'a' && c <= 'f');
    }

    // spec: fn getMaxChar
    private static int GetMaxChar(StringBuilder? buffer, int col)
    {
        if (buffer == null || buffer.Length == 0)
        {
            return -1;
        }

        string value = buffer.ToString();
        if (value[0] == '0')
        {
            throw new ArgumentException($"Leading zero not allowed in prefix modifier at col:{col}");
        }
        if (!int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out int n) || n < 1 || n > 9999)
        {
            throw new ArgumentException($"Prefix modifier out of range (1-9999) at col:{col}");
        }

        return n;
    }

    // returns true if expansion happened
    // spec: fn expandToken
    private static bool ExpandToken(
            Operator? op,
            string token,
            bool composite,
            int maxChar,
            bool firstToken,
            IReadOnlyDictionary<string, object> substitutions,
            StringBuilder result,
            int col)
    {
        if (string.IsNullOrEmpty(token))
        {
            throw new ArgumentException($"Empty variable name at col:{col}");
        }

        CheckVarname(token, col);

        object? value;
        substitutions.TryGetValue(token, out value);
        SubstitutionType substType = GetSubstitutionType(value, col);
        if (substType == SubstitutionType.EMPTY || IsEmpty(substType, value))
        {
            return false;
        }

        if (firstToken)
        {
            AddPrefix(op, result);
        }
        else
        {
            AddSeparator(op, result);
        }

        switch (substType)
        {
            case SubstitutionType.STRING:
                AddStringValue(op, token, value!, result, maxChar);
                break;
            case SubstitutionType.LIST:
                AddListValue(op, token, (IList)value!, result, maxChar, composite);
                break;
            case SubstitutionType.MAP:
                AddMapValue(op, token, (IDictionary)value!, result, maxChar, composite);
                break;
        }

        return true;
    }

    // spec: fn getSubstitutionType
    private static SubstitutionType GetSubstitutionType(object? value, int col)
    {
        if (value == null)
        {
            return SubstitutionType.EMPTY;
        }
        if (IsNativeType(value))
        {
            return SubstitutionType.STRING;
        }
        else if (IsList(value))
        {
            return SubstitutionType.LIST;
        }
        else if (IsMap(value))
        {
            return SubstitutionType.MAP;
        }
        else
        {
            throw new ArgumentException($"Illegal value type for substitution at col:{col}");
        }
    }

    // spec: fn isEmpty
    private static bool IsEmpty(SubstitutionType substType, object? value)
    {
        if (value == null)
        {
            return true;
        }
        else
        {
            switch (substType)
            {
                case SubstitutionType.STRING:
                    return false;
                case SubstitutionType.LIST:
                    return ((IList)value).Count == 0;
                case SubstitutionType.MAP:
                    return ((IDictionary)value).Count == 0;
                default:
                    return true;
            }
        }
    }

    // spec: fn isNativeType
    private static bool IsNativeType(object value)
    {
        return value is string or bool or int or long or float or double or decimal;
    }

    // spec: fn isList
    private static bool IsList(object value)
    {
        return value is IList;
    }

    // spec: fn isMap
    private static bool IsMap(object value)
    {
        return value is IDictionary;
    }

    // spec: fn convertNativeTypes
    private static string ConvertNativeTypes(object? value)
    {
        return value switch
        {
            string str => str,
            bool b => b ? "true" : "false",
            int number => number.ToString(CultureInfo.InvariantCulture),
            long number => number.ToString(CultureInfo.InvariantCulture),
            float number => number.ToString(CultureInfo.InvariantCulture),
            double number => number.ToString(CultureInfo.InvariantCulture),
            decimal number => number.ToString(CultureInfo.InvariantCulture),
            _ => throw new ArgumentException("Illegal value type for substitution"),
        };
    }

    // spec: fn addPrefix
    private static void AddPrefix(Operator? op, StringBuilder result)
    {
        switch (op)
        {
            case Operator.HASH:
                result.Append('#');
                break;
            case Operator.DOT:
                result.Append('.');
                break;
            case Operator.SLASH:
                result.Append('/');
                break;
            case Operator.SEMICOLON:
                result.Append(';');
                break;
            case Operator.QUESTION_MARK:
                result.Append('?');
                break;
            case Operator.AMP:
                result.Append('&');
                break;
            default:
                return;
        }
    }

    // spec: fn addSeparator
    private static void AddSeparator(Operator? op, StringBuilder result)
    {
        switch (op)
        {
            case Operator.DOT:
                result.Append('.');
                break;
            case Operator.SLASH:
                result.Append('/');
                break;
            case Operator.SEMICOLON:
                result.Append(';');
                break;
            case Operator.QUESTION_MARK:
            case Operator.AMP:
                result.Append('&');
                break;
            default:
                result.Append(',');
                break;
        }
    }

    // spec: fn addStringValue
    private static void AddStringValue(Operator? op, string token, object value, StringBuilder result, int maxChar)
    {
        AddValue(op, token, value, result, maxChar);
    }

    // spec: fn addListValue
    private static void AddListValue(Operator? op, string token, IList value, StringBuilder result, int maxChar, bool composite)
    {
        bool first = true;
        foreach (object? v in value)
        {
            if (first)
            {
                AddValue(op, token, v, result, maxChar);
                first = false;
            }
            else
            {
                if (composite)
                {
                    AddSeparator(op, result);
                    AddValue(op, token, v, result, maxChar);
                }
                else
                {
                    result.Append(',');
                    AddValueElement(op, token, v, result, maxChar);
                }
            }
        }
    }

    // spec: fn addMapValue
    private static void AddMapValue(Operator? op, string token, IDictionary value, StringBuilder result, int maxChar, bool composite)
    {
        if (maxChar != -1)
        {
            throw new ArgumentException("Prefix modifier is not allowed on map values");
        }
        bool first = true;
        // avoids foreach unboxing a nullable Current (CS8605)
        IDictionaryEnumerator entries = value.GetEnumerator();
        while (entries.MoveNext())
        {
            DictionaryEntry v = entries.Entry;
            if (composite)
            {
                if (!first)
                {
                    AddSeparator(op, result);
                }
                AddValueElement(op, token, (string)v.Key, result, maxChar);
                result.Append('=');
            }
            else
            {
                if (first)
                {
                    AddValue(op, token, (string)v.Key, result, maxChar);
                }
                else
                {
                    result.Append(',');
                    AddValueElement(op, token, (string)v.Key, result, maxChar);
                }
                result.Append(',');
            }
            AddValueElement(op, token, v.Value, result, maxChar);
            first = false;
        }
    }

    // spec: fn addValue
    private static void AddValue(Operator? op, string token, object? value, StringBuilder result, int maxChar)
    {
        switch (op)
        {
            case Operator.PLUS:
            case Operator.HASH:
                AddExpandedValue(null, value, result, maxChar, false);
                break;
            case Operator.QUESTION_MARK:
            case Operator.AMP:
                result.Append(token + '=');
                AddExpandedValue(null, value, result, maxChar, true);
                break;
            case Operator.SEMICOLON:
                result.Append(token);
                AddExpandedValue("=", value, result, maxChar, true);
                break;
            case Operator.DOT:
            case Operator.SLASH:
            case Operator.NO_OP:
                AddExpandedValue(null, value, result, maxChar, true);
                break;
        }
    }

    // spec: fn addValueElement
    private static void AddValueElement(Operator? op, string token, object? value, StringBuilder result, int maxChar)
    {
        switch (op)
        {
            case Operator.PLUS:
            case Operator.HASH:
                AddExpandedValue(null, value, result, maxChar, false);
                break;
            case Operator.QUESTION_MARK:
            case Operator.AMP:
            case Operator.SEMICOLON:
            case Operator.DOT:
            case Operator.SLASH:
            case Operator.NO_OP:
                AddExpandedValue(null, value, result, maxChar, true);
                break;
        }
    }

    // spec: fn addExpandedValue
    private static void AddExpandedValue(string? prefix, object? value, StringBuilder result, int maxChar, bool replaceReserved)
    {
        string stringValue = ConvertNativeTypes(value);
        List<int> s = new List<int>(stringValue.Length);
        for (int ci = 0; ci < stringValue.Length; ci += char.IsHighSurrogate(stringValue, ci) ? 2 : 1)
        {
            s.Add(char.ConvertToUtf32(stringValue, ci));
        }
        int max = (maxChar != -1) ? Math.Min(maxChar, s.Count) : s.Count;

        if (max > 0 && prefix != null)
        {
            result.Append(prefix);
        }

        int i = 0;
        while (i < max)
        {
            int c = s[i];
            if (IsUnreserved(c))
            {
                result.Append(char.ConvertFromUtf32(c));
            }
            else if (!replaceReserved && IsReserved(c))
            {
                result.Append(char.ConvertFromUtf32(c));
            }
            else if (!replaceReserved && c == '%' && i + 2 < max && IsHexDigit(s[i + 1]) && IsHexDigit(s[i + 2]))
            {
                result.Append(char.ConvertFromUtf32(c));
                result.Append(char.ConvertFromUtf32(s[i + 1]));
                result.Append(char.ConvertFromUtf32(s[i + 2]));
                i += 2;
            }
            else
            {
                PctEncode(c, result);
            }
            i++;
        }
    }

    // spec: fn isUnreserved
    private static bool IsUnreserved(int c)
    {
        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
            || c == '-' || c == '.' || c == '_' || c == '~';
    }

    // spec: fn isReserved
    private static bool IsReserved(int c)
    {
        return c <= 0x7F && ":/?#[]@!$&'()*+,;=".IndexOf((char)c) >= 0;
    }

    // spec: fn pctEncode
    private static void PctEncode(int c, StringBuilder result)
    {
        foreach (byte b in Encoding.UTF8.GetBytes(char.ConvertFromUtf32(c)))
        {
            result.Append('%');
            result.Append(b.ToString("X2"));
        }
    }
}
