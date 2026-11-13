package nz.studyguider

fun main() {
    val d = "$"
    // A saved answer splits into its text, tables and drawings, with a graph's description line taken with its image.
    val saved = "Working: ${d}v = f\\lambda$d\n\n| Ion | Charge |\n| --- | --- |\n| Fe | 3+ |\n\n![Drawing 1](/answer-images/42)\n\n![Graph 1](/answer-images/7)\nGraph 1: x-axis \"t\"."
    val parts = splitAnswer(saved)
    check(parts.text == "Working: ${d}v = f\\lambda$d") { parts.text }
    check(parts.tables == listOf(listOf(listOf("Ion", "Charge"), listOf("Fe", "3+"))))
    check(parts.images == listOf(AnswerImage(false, 42, "Drawing 1"), AnswerImage(true, 7, "Graph 1")))
    // Shown again: text, table, drawing, graph with its description, in reading order.
    val shown = shownBlocks(saved)
    check(shown.map { it::class.simpleName } == listOf("Text", "Table", "Image", "Image")) { shown.toString() }
    check((shown[3] as ShownBlock.Image).description == "x-axis \"t\".")
    check((shown[2] as ShownBlock.Image).path == "/answer-images/42")
    check(hasAnswerImages(saved) && !hasAnswerImages("![x](https://example.com/a.png)"))
    // Tables round-trip, escaping a bar inside a cell.
    val table = tableMarkdown(listOf(listOf("A", "B"), listOf("x | y", "line\nbreak")))
    check(table == "| A | B |\n| --- | --- |\n| x \\| y | line break |") { table }
    check(splitAnswer(table).tables.single()[1] == listOf("x | y", "line break"))

    // Symbols go in at the cursor, wrapped in dollars outside maths, and use the mhchem form inside \ce{}.
    check(insertSnippet("v = ", 4, 4, "\\frac{|}{}") == ("v = $d\\frac{}{}$d" to 11))
    check(insertSnippet("${d}x$d", 2, 2, "^{|}") == ("${d}x^{}$d" to 4))
    check(insertSnippet("$d\\ce{Fe}$d", 7, 7, "\\rightarrow ", "->").first == "$d\\ce{Fe->}$d")
    check(insertSnippet("ab", 0, 2, "\\sqrt{|}") == ("$d\\sqrt{ab}$d" to 9))
    check(appendEquation("Answer", "Fe^3+ + 3OH- -> Fe(OH)3(s)") == "Answer\n$d\\ce{Fe^3+ + 3OH- -> Fe(OH)3(s)}$d\n")

    // Graph description matches the web's wording: no ranges means grid squares from the origin (400, 280).
    val axes = GraphAxes("t", "s")
    check(formatPoint(axes, toData(axes, 440f to 200f)) == "(1, 2)")
    val curve = SketchItem("pen", listOf(320f to 360f, 360f to 240f, 400f to 200f, 440f to 240f, 480f to 360f))
    val text = describeGraph(axes, listOf(curve, SketchItem("point", listOf(400f to 280f)), SketchItem("text", listOf(440f to 200f), "max")))
    check(text.startsWith("x-axis \"t\", y-axis \"s\" (no scale given: positions are in grid squares from the origin).")) { text }
    check("Points plotted: (0, 0)." in text) { text }
    check("Curve 1 drawn from (-2, -2) to (2, -2); crosses the x-axis near x = -1.3, 1.3; crosses the y-axis near y = 2; maximum near (0, 2)." in text) { text }
    check("Labels: \"max\" at (1, 2)." in text) { text }
    val ranged = GraphAxes("x", "y", -5.0 to 5.0, 0.0 to 10.0)
    check(formatPoint(ranged, toData(ranged, 400f to 280f)) == "(0, 5)")
    check(describeGraph(ranged, emptyList()) == "x-axis \"x\" from -5 to 5, y-axis \"y\" from 0 to 10.")
    check(roundTo(0.30000000000000004, 0.1) == "0.3" && roundTo(-0.04, 0.1) == "0")

    // The eraser touches lines along their length and labels across their width.
    check(touches(SketchItem("line", listOf(0f to 0f, 100f to 0f)), 50f to 5f))
    check(!touches(SketchItem("line", listOf(0f to 0f, 100f to 0f)), 50f to 30f))
    check(touches(SketchItem("text", listOf(10f to 10f), "Cl"), 30f to 12f))

    // Multiple choice: the Choice line is first, keys alphabetical; working follows; an unreadable line means nothing chosen.
    check(choiceText(listOf("C", "A")) == "Choice: A, C" && choiceText(emptyList()) == "")
    check(choiceKeys("Choice: B\n\nMomentum is conserved.") == listOf("B"))
    check(choiceKeys("Choice: C, A") == listOf("A", "C"))
    check(choiceKeys("My choice is B").isEmpty() && choiceKeys("Choice: K").isEmpty())
    val chosen = splitAnswer("Choice: A, C\n\nBecause of the catalyst.")
    check(chosen.choice == listOf("A", "C") && chosen.text == "Because of the catalyst.") { chosen.toString() }
    check(splitAnswer("Plain answer").choice.isEmpty())

    // A lesson's choice block: stem, options with the correct one starred, then a reason per option.
    val quiz = parseLessonChoice("Which change increases the rate?\nA. Lowering the temperature\nB. Adding a catalyst *\nC. Larger lumps\n---\nB: A lower activation energy.\nA: Fewer collisions.".split("\n"))!!
    check(quiz.stem == "Which change increases the rate?" && quiz.options.map { it.key } == listOf("A", "B", "C"))
    check(quiz.options[1].correct && quiz.options[1].text == "Adding a catalyst" && quiz.options[1].explanation == "A lower activation energy." && !quiz.multiple)
    check(parseLessonChoice(listOf("No options here")) == null)
    // In the reader the block becomes one quiz, and its raw lines stay in the section text so saved-answer keys do not change.
    val chunk = lessonChunks("### Your Turn 1\nPick one.\n```choice\nWhich?\nA. One *\nB. Two\n```\nThen explain.").single()
    check(chunk.choices.single().range == 1..5 && chunk.choices.single().choice.options.size == 2) { chunk.choices.toString() }
    check(chunk.body == "Pick one.\n\n```choice\n\nWhich?\n\nA. One *\n\nB. Two\n\n```\n\nThen explain.") { chunk.body }
    // The new lesson structure: pre-questions are not practice; the last Your Turn is free recall.
    check(LessonChunk("Before you start", emptyList()).isPreQuestions && !LessonChunk("Before you start", emptyList()).isPractice)
    check(LessonChunk("Your Turn 4", listOf("paragraph" to "Without looking back, write the key ideas of this lesson.")).isFreeRecall)
    check(!LessonChunk("Your Turn 1", listOf("paragraph" to "Calculate the speed.")).isFreeRecall)
}
