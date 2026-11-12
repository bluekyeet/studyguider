# Answer forms in real NCEA papers

What a student actually has to produce in the answer spaces of NCEA Level 2 and 3 Chemistry, Physics,
Mathematics and Calculus exams, and how often each form occurs. The answer input (`server/web-answer.js`,
`server/answer_forms.py`) is built from this. Written 12 November 2026.

## Source and method

- Archive `NCEA-ARCH-L23-20261106-v1.zip`, 304 PDFs: 152 exam papers (`<standard>-exm-<year>.pdf`) and their 152
  assessment schedules (`-ass-`). Coverage: L3 Chemistry 91390/91391/91392, L3 Physics 91523/91524/91526 and
  L3 Calculus 91578/91579 for 2013-2025; L2 Mathematics 91261/91262/91267 for 2012-2025; L2 Chemistry
  91164/91165/91166 and L2 Physics 91170/91171/91173 for 2025 only. (The brief said 365 files; the archive holds 304.)
- Every exam paper was converted to text (`pdftotext -layout`) and split into its lowest-level parts ((a), (b)(i) ...),
  giving **2,445 answerable parts from 150 papers**. 91523 and 91524 for 2021 have no text layer and are not counted.
- Each part was classified by the instruction words it uses ("complete the table", "sketch", "draw the Lewis
  structure", "write an equation" ...). A part can have more than one form (a table plus an explanation).
- About 25 pages across all six subjects were rendered and checked by eye, to see the answer spaces themselves
  (ruled lines, empty boxes, blank tables, printed grids and axes) and to correct the keyword counts. The
  matching schedules were read to see what a marked answer contains.
- The counts are keyword counts, so treat them as close estimates. Where the eye check showed the keywords miss a
  form (mostly answer tables that the paper never introduces with "complete the table"), that is noted below.

## Summary

| Form | Parts | Share | Where it lives |
|---|---:|---:|---|
| Written explanation (prose lines) | ~1,190 | 49% | every subject; most L3 Chemistry and Physics parts |
| Calculation with numbers and units | ~955 | 39% | Physics, Chemistry, and the numeric half of the maths papers |
| Symbolic working (algebra, calculus) | ~800 | 33% | nearly every L2 Mathematics and L3 Calculus part |
| Organic structural formulae, reaction schemes | 88 | 4% (13% of L3 Chem) | 91391, 91165 |
| Chemical equations and K expressions | 49 | 2% (6% of L3 Chem) | 91392, 91390, 91166 |
| Graph to sketch or plot on printed axes or grid | 48 | 2% | 91262, 91524, 91526, one in 91166 |
| Table to complete or construct | 42 (+ unlabelled ones) | 2% (6% of L3 Chem) | 91390, 91391, 91267 |
| Diagram to draw (force, ray, wave, field, tree) | 42 | 2% (18% of L2 Physics) | 91523, 91524, 91170, 91171, 91173, 91267 |
| Label, circle or mark a supplied figure | 32 | 1% | 91391 (circle a functional group), 91524, 91523 |
| Lewis structure plus name of shape | 13 | one per 91390 paper | 91390, 91164 |
| Circle one printed option | 11 | <1% | 91390, 91164 |

Parts needing something other than text: **234 of 2,445 (10%)**, but unevenly spread: 19% of Chemistry parts,
20% of L2 Physics, 9% of L3 Physics, 5% of L2 Mathematics and 1% of L3 Calculus. 59 of those parts also need
a written explanation or a calculation in the same answer, and 31 need two non-text forms (a table whose
cells are drawn structures, say). So a single answer must be able to hold several forms.

What this means for the input:

1. Text with good maths and chemistry entry carries about 90% of all parts. It has to handle sub- and
   superscripts, units (m s⁻¹, kJ mol⁻¹), Greek letters, equilibrium arrows, state symbols, charges and set-out
   multi-line working. This matters more than anything else.
2. Drawing is next, and almost all of it is Chemistry structures and Physics diagrams on a blank box or
   over a printed figure.
3. Graph sketches are fewer but recur every year in 91262 (two per paper) and in 91524/91526. They are always on
   printed axes, usually a grid, often with "include values" or "label the intercepts".
4. Tables recur every year in 91390 and 91391, often with drawn structures in the cells.

## The forms, with examples

### Written explanation

Ruled lines under "Explain", "Justify", "Discuss", "Compare", "Evaluate". The schedules mark them as linked ideas
(the M and E columns ask for complete, linked explanations). Plain text, though explanations often include
a formula or equation in passing.
- L3 Chemistry 91390 2019 Q1(c)(i): "Explain why the radii of the S atom and the S²⁻ ion are different."
- L3 Physics 91524 2019 Q2(d): "Using physics principles, explain the effect this has on the rotational energy."
- L2 Mathematics 91262 2019 Q2(c): "Justify your choice of range(s) clearly."

### Calculation with numbers and units

"Calculate", "Show that", "Determine". The schedules expect the method, the substitution, the answer, units and
significant figures (for example 91390 2019 Q2(c)(i), whose schedule gives the expected method and value).
- L3 Chemistry 91390 2019 Q2(c)(i): ΔcH from 5.22 g of hexane heating 400 g of water, with c = 4.18 J g⁻¹ °C⁻¹.
- L3 Physics 91524 2019 Q1(c): minimum speed at the top of a vertical circle.
- L3 Physics 91524 2019 Q2(b)(i): "Show that the angular velocity of the system is 1.10 rad s⁻¹."

### Symbolic working (algebra and calculus)

"Differentiate", "Use calculus", "Find the equation of", "Solve", "Prove". The papers repeat "You must use calculus
and show any derivatives that you need". Working is multi-line, with fractions, powers, roots, e, ln, trig,
d/dx, ∫ and limits.
- L3 Calculus 91578 2019 Q1(c): gradient of the tangent to y = e²ˣ/(1 + x²) at x = 2.
- L3 Calculus 91578 2019 Q2(e): show that d²y/dx² = (d²y/du²)(du/dx)² + (dy/du)(d²u/dx²).
- L2 Mathematics 91262 2019 Q1(d): find the quadratic with given gradient, turning point and value.

### Chemical equations and equilibrium expressions

"Write an equation", "Write the expression for Ks". Need formulae with subscripts, states (s)(l)(g)(aq), charges as
superscripts, → and ⇌, and fraction-style K expressions with square brackets.
- L3 Chemistry 91392 2015 Q2(a)(i)-(ii): the equilibrium in saturated CaCO₃, then the expression for Ks(CaCO₃).
- L3 Chemistry 91392 2016 Q2(a): "Write an equation to show the reaction of ethanamine with water."
- L3 Chemistry 91390 2017 Q1(c)(i): an equation for the first ionisation energy of calcium.
- L2 Chemistry 91166 2025 Q2(c)(i): dissociation of each compound in water.

### Lewis structures and molecule shapes

Every 91390 paper has a table with a Lewis-structure row (an empty box per molecule) and a "Name of shape" row.
The schedule marks "Any two correct / Table correct", and the drawings themselves appear only as images in the
schedule, so a marker has to look at a drawing.
- L3 Chemistry 91390 2019 Q1(b): Lewis structure and name of shape for SF₄ and SF₃⁻ (table, checked by eye).
- L3 Chemistry 91390 2017 Q3(c)(i): "Draw the Lewis structure for the I₃⁻ ion in the box below."
- L2 Chemistry 91164 2025 Q3(c): Lewis structure (electron dot diagram) and shape for each molecule.

### Organic structural formulae and reaction schemes

Large empty boxes, or tables with a "Structural formula" column. Reaction schemes chain structures with reagents
and conditions written over arrows.
- L3 Chemistry 91391 2020 Q1(b): "Devise a reaction scheme to convert 1-bromobutane into butanoyl chloride",
  with reagents, conditions and the structure after each step, in one blank box (checked by eye).
- L3 Chemistry 91391 2015 Q1(b): table with names given and the structural formula to draw for each.
- L3 Chemistry 91391 2023 Q2(c)(iii): structures of the two products of hydrolysing a dipeptide.
- L2 Chemistry 91165 2025 Q2(a)(i): structures of compounds B, C and D in labelled boxes in a scheme.

### Tables to complete or construct

Printed tables with some cells filled (headers, row labels) and the rest blank. In 91390 and 91391 the keyword
count misses many, because the paper shows a table and asks e.g. "List all the forces of attraction" without
saying "complete the table". The eye check found answer tables in 91390 2019 Q1(a), Q1(b) and Q3(a) alone.
- L3 Chemistry 91390 2019 Q1(a): electron configurations of Cr, Fe³⁺, Ge in s, p, d notation (one column to fill).
- L3 Chemistry 91390 2019 Q3(a): attractive forces for NH₃, C₂H₆ and CH₃NH₂ (last column blank).
- L3 Chemistry 91390 2025 Q3(a)(i): an equation per substance in a table.
- L2 Mathematics 91267 2020 Q3(b)(i): complete a two-way table, then use it for a probability.

### Graphs to sketch or plot

Always on printed axes, mostly a grid; spare copies of the grid at the back of the paper. The schedules mark
features: shape, intercepts lined up with the turning points of the given graph, values on the axes, labels.
- L2 Mathematics 91262 2019 Q2(a): sketch y = f'(x) on blank axes under the given f(x) (checked by eye). Q2(d)
  sketches f(x) from f'(x). Both recur in every 91262 paper from 2012 to 2025.
- L3 Physics 91524 2019 Q3(c): on a grid, sketch displacement over three periods, including values for the time
  and the initial displacement (checked by eye).
- L3 Physics 91526 2013 Q1(c): "mark values on the axes and plot a curve with at least 3 points".
- L3 Physics 91526 2016 Q1(b): "Draw lines on the graph to help" find a resistance (draw on a given graph).
- L2 Chemistry 91166 2025 Q2(b)(i): add a second line to a given graph.

### Diagrams to draw or complete

Mostly drawing onto a supplied figure; sometimes an empty space.
- Force diagrams: L3 Physics 91524 2016 Q1(a) "draw labelled vectors showing the two forces acting on the car";
  91524 2023 Q1(a) vector diagram for the net force; L2 Physics 91171 2025 Q3(c)(i) "Add labelled arrows to the
  above diagram".
- Waves: L3 Physics 91523 2017 Q1(a) draw the fundamental standing wave and label the nodes; 91523 2025 Q2(a) the
  4th harmonic; L2 Physics 91170 2025 Q3(d)(ii) the result of two pulses interacting.
- Rays: L2 Physics 91170 2025 Q1(a) "Draw and label the image"; Q1(d)(i) "Complete the ray diagram".
- Fields: L2 Physics 91173 2025 Q1(a) field lines between charged plates.
- Probability trees: L2 Mathematics 91267 2022 Q3(b)(i) "Draw a probability tree".
- Enthalpy and energy-level diagrams and titration curves appear mostly as given figures to read from (for example
  the titration curve in 91392 2018 Q2(a)) rather than as answers. When they are answers, a sketch over a blank
  or gridded box covers them.

### Label, circle or mark a supplied figure

- L3 Chemistry 91391 2018 Q2(b)(i), 2022 Q2(c)(i), 2024 Q1(c)(i): circle the amide (peptide) bond on a printed dipeptide.
- L3 Chemistry 91391 2025 Q1(a)(i): mark each asymmetric carbon with an asterisk on a printed structure.
- L3 Physics 91523 2018 Q2(c): "Clearly mark on the diagram in Figure A the two positions ...".
- L3 Physics 91524 2019 Q1(d): "Include force labels on the diagram below to support your answer."

### Circle one printed option

- L3 Chemistry 91390 2019 Q2(a): circle Exothermic or Endothermic, then give a reason.
- L3 Chemistry 91390 2014 Q1(d)(ii): circle the atom with the greater electronegativity (Br, I).
- L2 Chemistry 91164 2025 Q2(a)(iv): circle the correct option for the sign of ΔrH.

These are answered fully by writing the choice, so they need no input of their own.

## From forms to inputs

| Form | Input | Notes |
|---|---|---|
| Prose, calculations, symbolic working | Text with a maths and chemistry toolbar and a rendered preview | Toolbar opens on the subject's palette (Chemistry, Maths/Calculus, Physics) |
| Chemical equations, K expressions | Same text input, chemistry palette, with a "type an equation" line that fills in `\ce{}` | mhchem is already loaded with KaTeX, so `Fe^3+ + 3OH- -> Fe(OH)3(s)` renders as written |
| Tables | Table input: the paper's headers and given cells, blank cells to fill; or a table the student builds | Saved as a Markdown table in the answer text |
| Graph sketches and plots | Graph input: axes with editable labels and optional ranges, grid, freehand curve, straight line, plotted points | The marker gets the image plus a text summary: axes, points, where each curve crosses the axes and its highest and lowest points |
| Diagrams; labelling a figure | Drawing canvas: pen, straight line, arrow, text label, eraser, undo, clear, over a blank box, a grid, or the question's own figure | Covers force, ray, wave and field diagrams, trees, circling and marking |
| Lewis structures, organic structures, reaction schemes | Drawing canvas (text labels for atom symbols, lines for bonds, arrows for scheme steps), or a photo of working on paper | A full chemical structure editor would be a heavy dependency for 4% of parts; not built |
| Anything else (long handwritten working, complex structures) | Photo upload of handwritten working | Existing Review upload; exams keep their paper mode |
