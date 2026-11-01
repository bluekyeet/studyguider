package nz.studyguider

fun main() {
    val parts = examParts("A trolley moves. (a) State the force. (b) (i) Calculate speed. (ii) Explain the change.")
    check(parts.map { it.first } == listOf("", "(a)", "(b)(i)", "(b)(ii)"))
    check(parts.last().second == "Explain the change.")
    check(examParts("Mass (kg) and time (s) are given.").size == 1)
}
