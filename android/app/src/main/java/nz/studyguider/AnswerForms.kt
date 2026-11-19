package nz.studyguider

import org.json.JSONArray
import org.json.JSONObject

/**
 * One kind of input an answer needs, as the server describes it (server/answer_forms.py). A question can ask for several; the
 * learner can always add another. A new kind of answer (multiple choice, say) is one more case here, one more block in
 * AnswerBox.kt, and one more way of writing it into the answer text.
 */
sealed class AnswerForm {
    /** Text with maths and chemistry entry; [palette] is the symbol set it opens on: chemistry, maths, physics or general. */
    data class Text(val palette: String = "general") : AnswerForm()

    /** A table: with [columns], complete the given one (blank cells are filled in); without, build your own. */
    data class Table(val columns: List<String> = emptyList(), val rows: List<List<String>> = emptyList()) : AnswerForm()

    /** A drawing on a blank box, a grid, or over the question's figure; [purpose] is lewis, structure, diagram or label. */
    data class Drawing(val background: String = "blank", val purpose: String = "") : AnswerForm()

    /** A sketch on axes, with optional labels and ranges. */
    data class Graph(val axes: GraphAxes = GraphAxes()) : AnswerForm()

    /**
     * Multiple choice (docs/api/multiple-choice.md): [options] are shown in the server's display order and lettered by position,
     * but an option's own key is what is sent. [multiple] is select all that apply. The correct answer is never in the form.
     */
    data class Choice(val options: List<ChoiceOption>, val multiple: Boolean = false, val instructions: String = "", val group: String = "",
                      val penalty: Double = 0.0) : AnswerForm()
}

data class ChoiceOption(val key: String, val text: String, val image: String = "")

/** The letter shown beside the option at [position]: A for the first shown, whatever its key. */
fun choiceLetter(position: Int) = ('A' + position).toString()

private fun JSONArray?.range(): Pair<Double?, Double?>? {
    if (this == null || length() != 2) return null
    val lo = if (isNull(0)) null else optDouble(0).takeIf { !it.isNaN() }
    val hi = if (isNull(1)) null else optDouble(1).takeIf { !it.isNaN() }
    return if (lo == null && hi == null) null else lo to hi
}

fun answerForm(json: JSONObject): AnswerForm? = when (json.optString("kind")) {
    "text" -> AnswerForm.Text(json.optString("palette", "general").ifBlank { "general" })
    "table" -> AnswerForm.Table(
        json.optJSONArray("columns")?.stringList().orEmpty(),
        json.optJSONArray("rows")?.let { rows -> (0 until rows.length()).map { rows.optJSONArray(it)?.stringList().orEmpty() } }.orEmpty(),
    )
    "drawing" -> AnswerForm.Drawing(json.optString("background", "blank").ifBlank { "blank" }, json.optString("purpose"))
    "graph" -> AnswerForm.Graph(GraphAxes(json.optString("x_label"), json.optString("y_label"),
        json.optJSONArray("x_range").range(), json.optJSONArray("y_range").range()))
    "choice" -> {
        val options = json.optJSONArray("options")?.objectList().orEmpty().map { ChoiceOption(it.optString("key"), it.optString("text"), it.stringOrNull("image").orEmpty()) }
            .filter { it.key.isNotBlank() }
        val order = json.optJSONArray("display_order")?.stringList().orEmpty()
        // Shown in the server's order; any option it left out keeps its place at the end.
        val shown = order.mapNotNull { key -> options.firstOrNull { it.key == key } } + options.filter { it.key !in order }
        if (shown.size < 2) null else AnswerForm.Choice(shown, json.optBoolean("multiple"), json.optString("instructions"), json.optString("group"),
            json.optDouble("penalty", 0.0).takeIf { !it.isNaN() } ?: 0.0)
    }
    else -> null
}

/** A list of forms from JSON, or null when the server gave none (an older question: the box then offers text only). */
fun answerForms(json: Any?): List<AnswerForm>? = (json as? JSONArray)?.let { array ->
    (0 until array.length()).mapNotNull { array.optJSONObject(it)?.let(::answerForm) }
}

/** Exam questions carry forms per part: {"": forms, "(a)": forms, ...}. A part falls back to the whole question's forms. */
fun partForms(question: JSONObject, label: String): List<AnswerForm>? {
    val byLabel = question.optJSONObject("answer_forms") ?: return answerForms(question.opt("answer_forms"))
    return answerForms(byLabel.opt(label)) ?: answerForms(byLabel.opt(""))
}

// ---- symbols ----------------------------------------------------------------------------------------------------------------

/** One button of the symbol bar: what it shows, its LaTeX ("|" is where the cursor lands), its name, and its mhchem form. */
data class Symbol(val label: String, val latex: String, val name: String, val ce: String? = null)

/** The same four sets as the web answer box. */
val SYMBOLS: Map<String, List<Symbol>> = linkedMapOf(
    "maths" to listOf(
        Symbol("a⁄b", "\\frac{|}{}", "Fraction"), Symbol("x²", "^{|}", "Power"), Symbol("xₙ", "_{|}", "Subscript"),
        Symbol("√", "\\sqrt{|}", "Square root"), Symbol("ⁿ√", "\\sqrt[]{|}", "nth root"), Symbol("×", "\\times ", "Times"),
        Symbol("÷", "\\div ", "Divide"), Symbol("±", "\\pm ", "Plus or minus"), Symbol("≠", "\\neq ", "Not equal"),
        Symbol("≈", "\\approx ", "Approximately"), Symbol("≤", "\\leq ", "Less than or equal"), Symbol("≥", "\\geq ", "Greater than or equal"),
        Symbol("π", "\\pi ", "Pi"), Symbol("θ", "\\theta ", "Theta"), Symbol("∞", "\\infty ", "Infinity"),
        Symbol("dy⁄dx", "\\frac{dy}{dx}", "dy by dx"), Symbol("d⁄dx", "\\frac{d}{dx}\\left(|\\right)", "Derivative of"),
        Symbol("∫", "\\int |\\,dx", "Integral"), Symbol("∫ₐᵇ", "\\int_{|}^{} \\,dx", "Definite integral"),
        Symbol("lim", "\\lim_{x \\to |}", "Limit"), Symbol("eˣ", "e^{|}", "e to the power"), Symbol("ln", "\\ln(|)", "Natural log"),
        Symbol("sin", "\\sin ", "Sine"), Symbol("cos", "\\cos ", "Cosine"), Symbol("tan", "\\tan ", "Tangent"),
        Symbol("|x|", "\\left|\\,|\\,\\right|", "Absolute value"), Symbol("Σ", "\\sum ", "Sum"), Symbol("→", "\\rightarrow ", "Arrow"),
        Symbol("⇒", "\\Rightarrow ", "Implies"),
    ),
    "chemistry" to listOf(
        Symbol("Chem", "\\ce{|}", "Chemical formula or equation"), Symbol("→", "\\rightarrow ", "Reaction arrow", "->"),
        Symbol("⇌", "\\rightleftharpoons ", "Equilibrium arrow", "<=>"), Symbol("x₂", "_{|}", "Subscript", "_"),
        Symbol("x⁺", "^{+}", "Positive charge", "^+"), Symbol("x⁻", "^{-}", "Negative charge", "^-"),
        Symbol("x²⁺", "^{2+}", "Charge 2+", "^2+"), Symbol("x²⁻", "^{2-}", "Charge 2−", "^2-"),
        Symbol("(s)", "\\text{(s)}", "Solid", "(s)"), Symbol("(l)", "\\text{(l)}", "Liquid", "(l)"), Symbol("(g)", "\\text{(g)}", "Gas", "(g)"),
        Symbol("(aq)", "\\text{(aq)}", "Aqueous", "(aq)"), Symbol("e⁻", "e^{-}", "Electron", "e-"), Symbol("[ ]", "[\\ce{|}]", "Concentration"),
        Symbol("Kₐ", "K_a", "Acid constant"), Symbol("Kₛ", "K_s", "Solubility product"), Symbol("ΔH", "\\Delta H", "Enthalpy change"),
        Symbol("ΔᵣH°", "\\Delta_r H^\\circ", "Standard reaction enthalpy"), Symbol("kJ mol⁻¹", "\\text{ kJ mol}^{-1}", "Kilojoules per mole"),
        Symbol("mol L⁻¹", "\\text{ mol L}^{-1}", "Moles per litre"), Symbol("δ+", "\\delta^{+}", "Partial positive"),
        Symbol("δ−", "\\delta^{-}", "Partial negative"), Symbol("a⁄b", "\\frac{|}{}", "Fraction"),
        Symbol("×10ⁿ", "\\times 10^{|}", "Times ten to the power"), Symbol("°", "^{\\circ}", "Degrees"),
    ),
    "physics" to listOf(
        Symbol("a⁄b", "\\frac{|}{}", "Fraction"), Symbol("x²", "^{|}", "Power"), Symbol("xₙ", "_{|}", "Subscript"),
        Symbol("√", "\\sqrt{|}", "Square root"), Symbol("×", "\\times ", "Times"), Symbol("×10ⁿ", "\\times 10^{|}", "Times ten to the power"),
        Symbol("≈", "\\approx ", "Approximately"), Symbol("Δ", "\\Delta ", "Delta"), Symbol("v⃗", "\\vec{|}", "Vector"),
        Symbol("Σ", "\\Sigma ", "Sum"), Symbol("m s⁻¹", "\\text{ m s}^{-1}", "Metres per second"),
        Symbol("m s⁻²", "\\text{ m s}^{-2}", "Metres per second squared"), Symbol("N", "\\text{ N}", "Newtons"),
        Symbol("J", "\\text{ J}", "Joules"), Symbol("W", "\\text{ W}", "Watts"), Symbol("Ω", "\\,\\Omega", "Ohms"),
        Symbol("Hz", "\\text{ Hz}", "Hertz"), Symbol("rad s⁻¹", "\\text{ rad s}^{-1}", "Radians per second"),
        Symbol("kg m²", "\\text{ kg m}^{2}", "Kilogram metre squared"), Symbol("°", "^{\\circ}", "Degrees"),
        Symbol("sin", "\\sin ", "Sine"), Symbol("cos", "\\cos ", "Cosine"), Symbol("π", "\\pi ", "Pi"),
    ),
    "greek" to listOf(
        Symbol("α", "\\alpha ", "Alpha"), Symbol("β", "\\beta ", "Beta"), Symbol("γ", "\\gamma ", "Gamma"), Symbol("δ", "\\delta ", "Delta"),
        Symbol("Δ", "\\Delta ", "Capital delta"), Symbol("ε", "\\varepsilon ", "Epsilon"), Symbol("θ", "\\theta ", "Theta"),
        Symbol("λ", "\\lambda ", "Lambda"), Symbol("μ", "\\mu ", "Mu"), Symbol("π", "\\pi ", "Pi"), Symbol("ρ", "\\rho ", "Rho"),
        Symbol("σ", "\\sigma ", "Sigma"), Symbol("τ", "\\tau ", "Tau"), Symbol("φ", "\\phi ", "Phi"), Symbol("ω", "\\omega ", "Omega"),
        Symbol("Ω", "\\Omega ", "Capital omega"),
    ),
)
val SYMBOL_SET_NAMES = mapOf("maths" to "Maths", "chemistry" to "Chemistry", "physics" to "Physics", "greek" to "Greek")
