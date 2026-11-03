package nz.studyguider

// Paper text comes out of the PDF without subscripts or superscripts ("CH3CH2OH", "mol–1"). This is display only: it never
// changes what is stored, and it only touches digits after real element symbols and exponents after unit symbols.
// The same rules as the website's scienceText, so both show a question the same way.
private val elements = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi U").split(" ").toSet()
private const val SUB = "₀₁₂₃₄₅₆₇₈₉"
private const val SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
private fun digits(text: String, table: String) = text.map { if (it in '0'..'9') table[it - '0'] else it }.joinToString("")
private val elementSymbol = Regex("[A-Z][a-z]?")
private val group = Regex("^(?:[A-Z][a-z]?\\d*)+$")
private fun isGroup(chunk: String) = group.matches(chunk) && elementSymbol.findAll(chunk).all { it.value in elements }
private fun isFormula(chunk: String) = chunk.any { it.isDigit() } && isGroup(chunk)

private val bracketed = Regex("\\(([A-Z][A-Za-z0-9]*)\\)(\\d+)")
private val formulaChunk = Regex("(?<![A-Za-z0-9])(\\d*)([A-Z][A-Za-z0-9]*)")
private val unitExponent = Regex("(?<![A-Za-z])(mol|kJ|kg|mg|cm|dm|mm|nm|Pa|Hz|[smgLJKVNWA])\\s?[–−-]\\s?(\\d)(?!\\d)")
private val mathSpan = Regex("\\$\\$[\\s\\S]+?\\$\\$|\\$[^$\\n]+\\$")

private fun plainScience(text: String): String = text
    .replace('', '→')
    .replace(bracketed) { m -> if (isGroup(m.groupValues[1])) "(${m.groupValues[1]})${digits(m.groupValues[2], SUB)}" else m.value }
    .replace(formulaChunk) { m ->
        val chunk = m.groupValues[2]
        if (isFormula(chunk)) m.groupValues[1] + Regex("\\d+").replace(chunk) { digits(it.value, SUB) } else m.value
    }
    .replace(unitExponent) { m -> m.groupValues[1] + "⁻" + digits(m.groupValues[2], SUP) }
    .replace(Regex("Δr(?=[A-Z])"), "Δᵣ")

/** Subscripts, unit exponents and arrows for plain paper text. Anything already written as LaTeX between dollar signs is left alone. */
fun scienceText(text: String): String {
    val out = StringBuilder()
    var index = 0
    for (match in mathSpan.findAll(text)) {
        out.append(plainScience(text.substring(index, match.range.first))).append(match.value)
        index = match.range.last + 1
    }
    return out.append(plainScience(text.substring(index))).toString()
}

/** Paper text keeps the PDF's line breaks: join them back into sentences, keeping blank lines and lines that start a source credit or a part. */
fun reflow(text: String): String = scienceText(
    text.replace(Regex("[ \\t]*\\n(?!\\s*\\n)(?!\\s*(?:Source|\\([a-hivx]+\\)))", RegexOption.IGNORE_CASE), " ").trim()
)
