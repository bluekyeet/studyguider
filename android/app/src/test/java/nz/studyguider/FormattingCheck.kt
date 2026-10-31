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
}
