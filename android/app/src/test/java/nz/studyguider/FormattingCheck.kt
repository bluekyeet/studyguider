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
}
