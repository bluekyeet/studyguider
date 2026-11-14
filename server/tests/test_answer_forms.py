"""Which answer inputs a question gets. The wording is taken from real NCEA papers (docs/design/answer-input-catalogue.md)."""
import answer_forms
from answer_forms import for_question, infer, merged, normalise


def kinds(forms):
    return [f["kind"] for f in forms]


def test_plain_explanations_and_calculations_get_text_only():
    assert infer("Explain why the radii of the S atom and the S2– ion are different.", "Chemistry") == [{"kind": "text", "palette": "chemistry"}]
    assert kinds(infer("Calculate the minimum speed Chris's centre of mass would need at the top.", "Physics")) == ["text"]
    assert infer("Differentiate y = 3x2 - 1.", "Calculus")[0]["palette"] == "maths"


def test_a_markdown_table_with_blank_cells_becomes_a_table_to_fill():
    forms = infer("Complete the table.\n\n| Symbol | Electron configuration |\n| --- | --- |\n| Cr |  |\n| Fe$^{3+}$ |  |", "Chemistry")
    assert forms[0] == {"kind": "table", "columns": ["Symbol", "Electron configuration"], "rows": [["Cr", ""], ["Fe$^{3+}$", ""]]}
    assert kinds(forms) == ["table", "text"]
    # A table the paper describes but does not lay out is one the learner builds.
    assert infer("Complete the following table.", "Chemistry")[0] == {"kind": "table", "columns": [], "rows": []}


def test_lewis_structures_and_organic_structures_are_drawn():
    lewis = infer("Complete the following table. SF4 SF3– Lewis structure Name of shape", "Chemistry")
    assert lewis[0] == {"kind": "drawing", "background": "blank", "purpose": "lewis"} and kinds(lewis) == ["drawing", "text"]
    # A Lewis structure the paper gives is read, not drawn.
    assert kinds(infer("The Lewis structure of ClF5 is given below. Identify and explain the shape and polarity of ClF5.", "Chemistry")) == ["text"]
    scheme = infer("Devise a reaction scheme to convert 1-bromobutane into butanoyl chloride.", "Chemistry")
    assert scheme[0]["purpose"] == "structure"


def test_graph_sketches_get_axes_and_drawing_on_a_given_figure_uses_it():
    graph = infer("Sketch the graph of the gradient function y = f'(x) on the axes below.", "Mathematics")
    assert graph[0]["kind"] == "graph" and graph[0]["x_label"] == "x"
    physics = infer("Draw a graph of circuit current against time for 15 seconds after the switch is closed.", "Physics")
    assert (physics[0]["y_label"], physics[0]["x_label"]) == ("circuit current", "time")
    on_figure = infer("Add a second line to the graph to predict the change in mass over time.", "Chemistry", has_figure=True)
    assert on_figure[0] == {"kind": "drawing", "background": "figure", "purpose": "label"}
    # "box plot" and "sketched below" describe something given, not something to draw.
    assert kinds(infer("The box plot below shows the data, as sketched below.", "Mathematics")) == ["text"]


def test_diagrams_and_labels_draw_over_the_figure_when_there_is_one():
    forces = infer("On the diagram above, draw labelled vectors showing the two forces acting on the car.", "Physics", has_figure=True)
    assert forces[0]["background"] == "figure"
    assert infer("Draw the field lines between the electric plates.", "Physics")[0] == {"kind": "drawing", "background": "blank", "purpose": "diagram"}
    assert infer("Circle the amide (peptide) bond.", "Chemistry", has_figure=True)[0]["purpose"] == "label"
    # A prize draw and a bottle's label are not drawing instructions.
    assert kinds(infer("Customers who spend over $100 go into a draw to win a prize. The label on the bottle says 300 g.", "Mathematics")) == ["text"]


def test_model_forms_are_checked_and_always_keep_text():
    assert normalise([{"kind": "graph", "x_label": "t / s", "x_range": [0, 10], "y_range": [5, 1]}]) == [
        {"kind": "graph", "x_label": "t / s", "y_label": "", "x_range": [0, 10], "y_range": None},
        {"kind": "text", "palette": "general"}]
    assert normalise([{"kind": "video"}, "nonsense"]) is None
    assert normalise("text") is None
    # A stored "general" palette defers to the subject.
    assert normalise([{"kind": "text", "palette": "general"}], "Physics") == [{"kind": "text", "palette": "physics"}]


def test_a_paper_question_gets_forms_per_answerable_part_from_its_own_lines():
    text = ("QUESTION ONE\n(a)\nComplete the following table.\nSymbol\nCr\n(b)\nComplete the following table.\nSF4\nLewis structure\n"
            "Name of shape\n(c)\n(i)\nExplain why the radii differ.\n(ii)\nJustify the difference.")
    parts = [{"label": "context", "text": "QUESTION ONE"}, {"label": "a", "text": "(a)\nComplete the following table."},
             {"label": "b", "text": "(b)\nComplete the following table."}, {"label": "c", "text": "(c)"},
             {"label": "c(i)", "text": "(i)\nExplain why the radii differ."}, {"label": "c(ii)", "text": "(ii)\nJustify the difference."}]
    forms = for_question(text, "Chemistry", parts)
    assert set(forms) == {"", "a", "b", "c(i)", "c(ii)"}           # (c) only introduces its sub-parts
    assert kinds(forms["a"]) == ["table", "text"]
    assert forms["b"][0]["purpose"] == "lewis"                     # the table's words are in the question text, not the part
    assert kinds(forms["c(i)"]) == ["text"]
    stored = for_question(text, "Chemistry", parts, {"a": [{"kind": "graph"}]})
    assert kinds(stored["a"]) == ["graph", "table", "text"]      # a stored form adds to the table the wording asks for


def test_a_single_answer_box_merges_its_parts_forms():
    assert kinds(merged({"": [{"kind": "text", "palette": "physics"}], "c": [{"kind": "graph"}, {"kind": "text", "palette": "physics"}]})) == ["graph", "text"]


def test_the_generation_prompt_names_every_kind():
    # Multiple choice is asked for only when the paper is assessed that way, with its own prompt (choice.PROMPT).
    import choice
    for kind in answer_forms.KINDS:
        assert f'"kind": "{kind}"' in (choice.PROMPT if kind == "choice" else answer_forms.PROMPT)


def test_the_wording_wins_over_a_stated_text_only_form():
    # The revision-pack question that came back from the model with only [{"kind": "text"}].
    question = "Draw the Lewis structure, name the shape, and determine the polarity of $\text{SF}_4$."
    forms = answer_forms.resolve([{"kind": "text"}], "Chemistry", question)
    assert [f["kind"] for f in forms] == ["drawing", "text"] and forms[0]["purpose"] == "lewis"
    for wording, kind in (("Sketch the graph of y = f'(x) on the axes below.", "graph"),
                          ("Complete the table below for each compound.", "table"),
                          ("Plot the points and draw a line of best fit.", "graph"),
                          ("Label the nodes on the diagram below.", "drawing")):
        assert kind in [f["kind"] for f in answer_forms.resolve([{"kind": "text"}], "Physics", wording, has_figure=True)], wording


def test_a_stated_form_can_add_but_not_take_away():
    stated = [{"kind": "drawing", "background": "blank", "purpose": "diagram"}, {"kind": "text"}]
    forms = answer_forms.resolve(stated, "Physics", "Sketch a graph of velocity against time for the car.")
    assert [f["kind"] for f in forms] == ["drawing", "graph", "text"]
    stated = [{"kind": "graph", "x_label": "t", "y_label": "v"}, {"kind": "text"}]
    # A question whose wording asks for nothing special keeps exactly what was stated.
    assert [f["kind"] for f in answer_forms.resolve(stated, "Physics", "Explain why the car slows down.")] == ["graph", "text"]


def test_a_multiple_choice_question_keeps_its_stated_forms():
    stated = [{"kind": "choice", "options": [{"text": "A sketch"}, {"text": "A table"}]}, {"kind": "text"}]
    forms = answer_forms.resolve(stated, "", "Which graph shows the sketch of y = x^2?")
    assert [f["kind"] for f in forms] == ["choice", "text"]


def test_stored_forms_of_older_questions_gain_what_their_wording_requires():
    forms = answer_forms.for_question("(a) Complete the table.\n| Ion | Charge |\n| --- | --- |\n| Na | |", "Chemistry",
                                      [{"label": "a", "text": "(a) Complete the table.\n| Ion | Charge |\n| --- | --- |\n| Na | |"}],
                                      {"a": [{"kind": "text"}]})
    assert forms["a"][0]["kind"] == "table" and forms["a"][0]["columns"] == ["Ion", "Charge"]
    # Generated questions go through the same rule.
    made, _, _ = answer_forms.with_choice([{"kind": "text"}], None, "Chemistry", "Draw the structural formula of the products.")
    assert [f["kind"] for f in made] == ["drawing", "text"]
