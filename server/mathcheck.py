"""Check the arithmetic in AI-written text in code, not by asking a model.

A lesson, marking guide or answer key written by the model can state a sum that is wrong ("128 + 32 + 4 + 2 = 174", which leaves
out the 8), and a reviewing model can miss it. Here every stated calculation whose sides are plain numbers is evaluated with a
small, safe expression evaluator (Python's parser, numbers and + - * / ^ sqrt only, nothing else is ever run), and the stated
result compared within the rounding it was written to. Unit conversions within one unit ("2.5 km = 2500 m", "350 mL = 0.35 L")
are checked the same way.

Anything with a variable, a function other than sqrt, or a unit inside the working is skipped: this finds wrong arithmetic,
it does not judge a method. What it finds goes back to the writer for correction, and is shown as a warning when that fails.
"""
import ast
import math
import operator
import re

_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}
# A number written with thousands separators ("27,086") or as a power of ten.
_THOUSANDS = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})+(?![\d,])")
_ARITH = re.compile(r"^[\d.\s+\-*/()^]+$")
PREFIX = {"G": 1e9, "M": 1e6, "k": 1e3, "": 1.0, "c": 1e-2, "m": 1e-3, "μ": 1e-6, "µ": 1e-6, "u": 1e-6, "n": 1e-9}
BASE_UNITS = ("g", "m", "L", "J", "W", "Pa", "s", "Hz", "V", "A", "N", "mol", "Wh", "B")
_UNIT = re.compile(r"(-?\d+(?:\.\d+)?(?:\s*\*\s*10\s*\^\s*\(?-?\d+\)?)?)\s*(G|M|k|c|m|μ|µ|n)?(" + "|".join(sorted(BASE_UNITS, key=len, reverse=True)) + r")\b")


class _Unsafe(ValueError):
    pass


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _evaluate(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 64 or abs(left) > 1e12):
            raise _Unsafe("power too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sqrt" and len(node.args) == 1 and not node.keywords:
        value = _evaluate(node.args[0])
        if value < 0:
            raise _Unsafe("square root of a negative number")
        return math.sqrt(value)
    raise _Unsafe(type(node).__name__)


def evaluate(expression):
    """The value of a plain arithmetic expression, or None when it is not one."""
    source = expression.replace("^", "**")
    if len(source) > 300:
        return None
    try:
        return _evaluate(ast.parse(source, mode="eval"))
    except (SyntaxError, _Unsafe, ZeroDivisionError, OverflowError, ValueError, TypeError, RecursionError):
        return None


def plain(text):
    """LaTeX and typeset maths turned into plain arithmetic: \\frac{a}{b} -> ((a)/(b)), \\times -> *, x² -> x^2, 10^{3} -> 10^(3)."""
    text = text.replace("$", " ")
    text = re.sub(r"\\(?:text|mathrm|textrm|mathbf)\{([^{}]*)\}", r" \1 ", text)
    for _ in range(4):      # nested fractions and roots
        text = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", text)
        text = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", text)
    text = re.sub(r"\\(?:times|cdot|ast)", "*", text)
    text = re.sub(r"\\div", "/", text)
    text = re.sub(r"\\approx|≈", " ≈ ", text)
    text = re.sub(r"\\(?:left|right|,|;|!|quad|qquad)", " ", text)
    text = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", text)
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
    text = re.sub(r"([\d)])([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)", lambda m: m.group(1) + "^(" + m.group(2).translate(_SUPERSCRIPT) + ")", text)
    text = _THOUSANDS.sub(lambda m: m.group(0).replace(",", ""), text)
    text = re.sub(r"(?<=\d)\s*x\s*(?=\d)", " * ", text)        # "3 x 4" written for 3 times 4
    return text


def _tail(side):
    """The arithmetic at the end of the text before '=' ("so the total is 128 + 32" -> "128 + 32")."""
    match = re.search(r"((?:sqrt\()?[\d.(][\d.\s+\-*/()^]*(?:sqrt\([\d.\s+\-*/()^]*\)[\d.\s+\-*/()^]*)*)$", side.rstrip())
    return match.group(1).strip() if match else ""


def _head(side):
    """The arithmetic at the start of the text after '=' ("174 kJ" -> "174")."""
    match = re.match(r"\s*(-?\s*(?:sqrt\()?[\d.(][\d.\s+\-*/()^]*(?:sqrt\([\d.\s+\-*/()^]*\)[\d.\s+\-*/()^]*)*)", side)
    if not match:
        return ""
    head = match.group(1).strip()
    # "= 3.0 v" is 3.0 times v, not the number 3.0: a single letter that is not a unit symbol makes it algebra.
    if re.match(r"\s*\*?\s*[a-zA-Zα-ω](?![a-zA-Z])", side[match.end():]) and not re.match(r"\s*[msgNJKWVALCTh]\b", side[match.end():]):
        return ""
    # Stop before a sentence's full stop, a trailing operator or a dangling open bracket left by the text that follows.
    head = re.sub(r"[\s+\-*/^(.]+$", "", head)
    return head if head.count("(") == head.count(")") else ""


def _has_operator(expression):
    return bool(re.search(r"\d\s*[+\-*/^]\s*[\d(s]|sqrt", expression.lstrip("-")))


def _close(computed, stated_text, approximate):
    stated = evaluate(stated_text)
    if stated is None:
        return True
    if approximate:
        return abs(computed - stated) <= max(abs(stated) * 0.02, 1e-9)
    tolerance = 1e-9 + abs(stated) * 1e-9
    number = re.fullmatch(r"-?\s*(\d+)(?:\.(\d+))?", stated_text.replace(" ", ""))
    if number:
        decimals = len(number.group(2) or "")
        tolerance = max(tolerance, 0.5 * 10 ** -decimals + 1e-9)
        digits = (number.group(1).lstrip("0") + (number.group(2) or "")).rstrip("0") if decimals == 0 else (number.group(1).lstrip("0") + number.group(2)).lstrip("0")
        if decimals == 0 and len(digits) <= 3 and abs(stated) >= 100:
            tolerance = max(tolerance, 0.5 * 10 ** (len(number.group(1)) - len(digits)))   # "27100" written to three figures
    return abs(computed - stated) <= tolerance


def _scaled(computed, stated):
    """True when the two differ by a power of 1000 or 1024 (a unit prefix such as kilo or mega), to three figures."""
    if not stated or not computed:
        return False
    for base in (1000, 1024):
        for power in range(-3, 4):
            if power and abs(computed / base ** power - stated) <= abs(stated) * 0.005:
                return True
    return False


def arithmetic_problems(text):
    """[{"claim", "computed", "stated"}] for each stated calculation in the text whose result is wrong."""
    problems = []
    for line in plain(text or "").splitlines():
        pieces = re.split(r"(=|≈)", line)
        for index in range(0, len(pieces) - 2, 2):
            left, sign, right = pieces[index], pieces[index + 1], pieces[index + 2]
            expression, result = _tail(left), _head(right)
            if not expression or not result or not _ARITH.match(expression.replace("sqrt", "")) or not _ARITH.match(result.replace("sqrt", "")):
                continue
            # A claim is a calculation on one side and its value on the other ("x = 5" alone is a statement, not a sum).
            if not (_has_operator(expression) or _has_operator(result)):
                continue
            computed, other = (evaluate(expression), result) if _has_operator(expression) else (evaluate(result), expression)
            if computed is None or evaluate(other) is None:
                continue
            # "1500 × 1000 = 1.5 megapixels", "27086 = 27.1 kJ": a result followed by a unit may carry a scale in that unit.
            if other is result and re.match(r"\s*[A-Za-zμµΩ]{2,}", right[right.find(result) + len(result):]) and _scaled(computed, evaluate(other)):
                continue
            if not _close(computed, other, sign == "≈"):
                problems.append({"claim": f"{expression} {sign} {result}", "computed": round(computed, 6), "stated": evaluate(other)})
    return problems + unit_problems(text)


def unit_problems(text):
    """Conversions within one unit that are wrong: "2.5 km = 250 m", "350 mL = 3.5 L"."""
    problems = []
    flat = plain(text or "")
    for match in re.finditer(r"(" + _UNIT.pattern + r")\s*=\s*(" + _UNIT.pattern + r")", flat):
        left = _UNIT.fullmatch(match.group(1).strip())
        right = _UNIT.fullmatch(match.group(5).strip())
        if not left or not right or left.group(3) != right.group(3) or (left.group(2) or "") == (right.group(2) or ""):
            continue
        a, b = evaluate(left.group(1)), evaluate(right.group(1))
        if a is None or b is None:
            continue
        expected = a * PREFIX[left.group(2) or ""] / PREFIX[right.group(2) or ""]
        if not _close(expected, right.group(1).replace(" ", ""), False) and abs(expected - b) > abs(expected) * 0.005:
            problems.append({"claim": match.group(0).strip(), "computed": expected, "stated": b})
    return problems


def describe(problems, limit=6):
    """Problems as sentences for a writer to fix, or for a learner to see as a warning."""
    return [f"The working states {p['claim']}, but that comes to {_number(p['computed'])}, not {_number(p['stated'])}."
            for p in problems[:limit]]


def _number(value):
    return f"{value:.6g}"


def issues(text):
    """Arithmetic problems as review issues for a writer, in the reviewer's form."""
    return ["Arithmetic error: " + sentence + " Correct the working and everything that depends on it." for sentence in describe(arithmetic_problems(text))]


WARNING = "Check the arithmetic: "


def warning(problems):
    """A note to show with AI-written working that is still wrong after it was sent back for correction."""
    return WARNING + " ".join(describe(problems)) if problems else ""
