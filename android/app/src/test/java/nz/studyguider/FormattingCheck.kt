package nz.studyguider

fun main() {
    check(inlineRuns("**Force:** value").first().bold)
    check(inlineRuns("$" + "v_i = 0" + "$" ).single().text.contains("v_i"))
    check(practiceQuestions("1. Displacement ($" + "s" + "$) is a change in position measured in metres.")
        .none { it.kind == PracticeQuestion.Kind.BlankFormula })
    val definitions = "**Velocity:** Rate of change of displacement.\n**Force:** A push or pull on an object.\n**Mass:** Amount of matter in an object."
    val multipleChoice = practiceQuestions(definitions).first()
    check(multipleChoice.choices.size == 3)
    check(multipleChoice.answer in multipleChoice.choices)
    check(practiceQuestions("Explain why a force changes the motion of an object.").all { it.choices.isEmpty() })
    val equations = "1. ${'$'}v = u + at${'$'}\n2. ${'$'}s = ut + 0.5at^2${'$'}\n3. ${'$'}v^2 = u^2 + 2as${'$'}"
    check(practiceQuestions(equations).isEmpty())
    check(practiceQuestions("1 C: **meth-** (S1)\n2 C: **eth-** (S1)\n3 C: **prop-** (S1)\n4 C: **but-** (S1)").isEmpty())
    check(practiceQuestions("**Assumed Prior Knowledge:** This is the first lesson in the Organic Chemistry course. It assumes basic atomic structure and covalent bonding.").isEmpty())
    check(practiceQuestions("By the end of this lesson, you will be able to define organic compounds and identify key functional groups.").isEmpty())
    // A quote inside a formula must not be able to end the data-tex attribute and add an event handler.
    val hostile = KaTeX.toHtml("${'$'}x\" onmouseover=\"alert(1)${'$'}")
    check("onmouseover=\"" !in hostile && hostile.count { it == '"' } == 4) { hostile }
    check("&quot;" in hostile)
    check(withoutSourceMarkers("review [5d374a3f-74f2-412a-8f6a-b582963eb2e0, learner_answers].") == "review.")
    check(withoutSourceMarkers("review [S1, learner_answers].") == "review.")
    check(withoutSourceMarkers("carbon (, p. 1). series (, p. 1;, p. 2).") == "carbon. series.")
    check(withoutSourceMarkers("AS 91166 (Resource ID: `abc3458d-b975-4d7f-8d04-35513966b94f`, p. 1), including") == "AS 91166, including")
    check(withoutSourceMarkers("(\"Demonstrate\", Resource ID: `3206fc65-14f9-4563-a428-f7c18863a105`, p. 1)") == "(\"Demonstrate\")")
    check(withoutSourceMarkers("see (Data booklet, p. 4) ok") == "see (Data booklet, p. 4) ok")
    check(scienceText("Ca(OH)2 and Fe2O3 and 91164 Q1") == "Ca(OH)₂ and Fe₂O₃ and 91164 Q1")
    check(scienceText("keep ${'$'}H2O${'$'} as is") == "keep ${'$'}H2O${'$'} as is")
}
