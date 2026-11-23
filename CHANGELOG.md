# Changes

## Next

**Pens**
- A picture as a drawing: File → Open a picture as a drawing… (or Open, for PNG, JPG, BMP, GIF,
  WebP) draws a photo with lines, in three styles: waves (rows that wobble like a seismograph's
  trace, higher and faster where it is darker), a spiral (one line from the middle out) and
  hatching (an engraving: one, two or three directions by the darkness). Width, line spacing, the
  waves' height and density or the hatching's angle, contrast, brightness, invert, lifting the pen on
  white and one joined line, with a live preview, its size and the length to draw. With the knife
  the pen is offered first.

**Drawing and files**
- Trace a picture into shapes (File menu; Open does it with a picture when the tool is the knife): a
  logo or a picture's dark areas become shapes to cut, their holes too, with the width, threshold,
  specks left out, detail, smooth curves and invert, and a live preview. The tracer is Kerfly's.
- A picture given at the start (`vintyl photo.jpg`) opens too.
- Weld a text's letters (the button beside italic): where they overlap (script fonts, tight spacing)
  they become one outline, so the knife does not cut inside the word; the holes stay, and the text
  stays editable (it is welded again when it changes). The text fields are a little narrower, so the
  bar still fits a 1366 px screen in every language.

**Faster**
- Big drawings (a photo as lines, tens of thousands of points): an element's box, polylines and
  outline are worked out once, until it changes; the sheet draws a big element line by line with a
  thin line (a zoom step from 0.7 s to a few ms); the job (the cut length, the knife path) is worked
  out a moment after the last change, not at every click.

## 0.9.1

An outline and its fill in two colours, and a colour can be removed.

**Colours**
- An outline and its fill in two colours, drawn with two pens (a black outline, a pink fill): the
  Fill window (and the bucket in the Colours panel) chooses the fill's colour: as the shape, another
  colour of the design, or a new one, put before the outline's so the outline is drawn last. The
  Colours list counts and selects a shape under both colours. Saved in the project (a fill's
  "layer"); an older Vintyl draws such a fill in the outline's colour.
- Opening an SVG: a shape with a stroke of another colour than its fill (a pink shape with a black
  edge) opens as a black outline with a pink fill; the colours window lists both colours, its
  picture shows the fills, and a colour that only fills others is drawn first.
- Remove this colour (the right mouse button on a colour in the panel, with its settings and its
  fill): its elements go to the first other colour, the fills it drew to their shapes' own colour.
- The Colours list shows up to four colours and scrolls the rest, so the element list keeps its
  room on a 768 px screen.
- A fill in a new colour is previewed on the sheet in that colour while the Fill window is open.

**Fixed**
- Moving the first colour in the Colours panel (or putting a new one before it) no longer gives its
  colour to the shapes drawn before the design had colours.

**Changed**
- Zooming out stops at the whole sheet (100%), which then sits where Fit puts it and follows the
  window's size again; zooming in has no such limit.

## 0.9.0

Colours: a design of several colours, drawn with several pens or cut from
several colours of vinyl, one colour after another.

**Colours**
- An SVG of several colours opens in its colours. A window shows each colour of the file and the
  colour of the design it goes to: similar colours (delta E under 15: two pinks, two greys) are
  merged, so one pen draws them; or each on its own; or all in one colour, as before. Gradients
  count as their first colour; invisible shapes are left out. Shapes filled in the file get a line
  fill for the pen.
- The Colours panel (when there is more than one): the order they are drawn in, a colour left out,
  a click selects its elements, and each colour's name, colour, pen width and where its stroke lies.
  On the sheet and in the element list every element shows in its colour.
- A fill for a whole colour (the bucket in the Colours panel, with the pen): every closed shape of
  that colour gets the pattern, in the same window as Fill; the list shows it beside the colour.
- The right mouse button → Colour moves elements to another colour, or to a new one.
- Start goes colour after colour: the check list names them in order, and before each a window asks
  to put in its pen (or its vinyl), with Skip this colour and Finish. All the colours keep the same
  origin, so they land exactly on each other.
- Save .hpgl writes one file for each colour.
- Settings → Drawing: what the colours window proposes first, Merge similar or Each on its own.
- A demo to try it: docs/demo/vintyl-demo.svg, Vintyl's logo and name in nine colours (five when
  merged).
- Projects keep their colours. A project without them (from an older Vintyl) opens in one colour.

## 0.8.1

Four more languages, and small fixes.

**Languages**
- German, Spanish, French and Brazilian Portuguese, besides English and Polish (the languages of
  Kerfly, and Portuguese for Brazil). A system in Portuguese gets the Brazilian translation. Numbers
  are written with a decimal comma where the language does.
- The window fits a 1366 px screen in every language: the ribbon and the tool strip may use shorter
  words than the menus.

**Materials**
- Reflective vinyl: the 60° blade with its 0.50 mm knife offset (Roland's blade guide).

**Fixed**
- The cutter settings and materials windows scroll their cards when made low, instead of squeezing
  them over each other.
- The window fits a 1366 px screen also with a wide system font (DejaVu Sans): the ribbon and the
  selection bar are a little tighter, and a tool's name too long for its tile is a pixel smaller.

**For developers**
- Tests on GitHub after every push (Linux, Python 3.12 and 3.13, DejaVu Sans): the self-test, all
  the tests and the translations' check.
- From the source, Vintyl needs Python 3.12 or newer: with 3.11, PySide6 miscounts None and Python
  aborts. The AppImage has its own Python and is not affected.

## 0.8.0

A new look for the whole window (UI v2), and materials. A big step, so the
number jumps from 0.2 to 0.8: the cutters are tested and cut cleanly, and
1.0 is near.

**Materials**
- A material keeps how to cut or draw it: the tool, the force and speed for each cutter, the blade,
  knife offset and overcut, the mirror, the weeding frame and a note. Built in: vinyl film, heat
  transfer vinyl, reflective vinyl, paper with a fineliner, card with a marker; add your own.
- Choosing a material sets the job's switches; it is remembered for each cutter and in the project.
- A cutter that takes force and speed from its panel only gets them shown in large type before Start.
- Starting force and speed in the built-in materials for the cutters with the XILI board (VEVOR,
  Seiki), all at 300 mm/s. The big 870 mm cutters: vinyl 80 g, heat transfer vinyl 120 g, reflective
  80 g, pens 70 g; the small KI-375A (and another model) presses harder: half (vinyl 50 g). Check
  them with the knife test.

**The window**
- Light and dark looks in the same style for every window; the cutter, the tool and the material
  in the left panel, with the cutter's state and what to do when its port cannot be used.
- The selection bar shows the type and name of what is selected; a text's fields have a second row;
  the ruler's result is shown in it too. Fits a 1366 × 768 screen in every state.
- The element list shows the cutting order and scissors to leave an element uncut; the right button
  on it opens the same menu as on the sheet (duplicate, delete, cutting order...).
- The sheet has rulers in mm, sizes beside the selection and zoom buttons.
- Start, Save .hpgl and the knife test stay at the bottom of the left panel, always in sight;
  Stop takes Start's place while sending, with the percentage sent.
- Speeds in mm/s.

**Placing**
- To 0,0 (Ctrl+Home, as Kerfly's "design to the head"): the selected elements, or the whole design
  as it is laid out, go together up to the origin, where the cutter's head starts; room is left for
  the weeding frame and the knife.

**Windows**
- The check list before Start and the knife test are windows of their own, with the material's
  values; a yellow warning when the mirror is on.
- Pattern of shapes and Fill show a preview of the shape in the window; the fill patterns are
  buttons with their pictures.
- Ready shapes show their picture beside the fields; questions say what their button does.
- Settings, cutter settings and materials as cards with switches.
- About, Keyboard shortcuts (in groups, with a search), Diagnostic report and Access to the cutter
  (the commands to copy); the new-version bar under the ribbon.
- `vintyl --self-test` checks the built-in materials too.

**Website and guide**
- A website with a user guide, in English and Polish: https://cyryllo.github.io/vintyl/
- The README rewritten; credits for the code from Kerfly and K40 Whisperer and for the programs
  studied (Inkcut, CutScape, RedsailCut) in the README and THIRD-PARTY-NOTICES.md.

**Fixed**
- Help → About, Keyboard shortcuts and Access to the cutter open again (they were built but not shown).
- The mouse wheel changes a list or a number field only once it is clicked; scrolling a panel no
  longer changes the values passing under the mouse.
- Dragging a small square round the selection resizes the shape again: the square lost the drag
  at the first move, so the shape moved a little and went back to its size.

## 0.2.0

The second test version (Linux, AppImage). Still tested on the VEVOR KI-375A
only; the larger cutters' profiles are to be checked on the machines. Please
tell us how it works on yours: Help → Diagnostic report → "Report my cutter".

**For vinyl**
- Mirror for heat transfer vinyl: one switch in the Job; the screen shows the design as on the shirt.
- Knife test: a 15 mm square with a triangle, cut near the origin to check the force.
- Copies in rows and columns, a gap apart (or as many as fit in the width).
- Weeding lines: cuts through the waste between the shapes, up to the weeding frame.
- Split into strips: a design wider than the cutter (or longer than a sheet) in overlapping strips,
  laid one after another on the material.

**Drawing and files**
- Text on a path: a text along a line, a curve or round a circle (letters keep their curves).
- Open DXF drawings (units from the file, asked when it has none).
- The rectangle tool has a corner radius; turn the selection by any angle; a right-click menu.

**The program**
- Settings: language (as the system, English, Polski) and look (light, dark, as the system).
- A new version is announced in the window (asks GitHub at most once a day; can be turned off).
- From the AppImage: add Vintyl to the applications menu (asked once, or Help menu).
- Help → Diagnostic report: versions, checks, the cutter and the log, to paste into an issue;
  GitHub forms to report a problem or how Vintyl works on your cutter.

## 0.1.0a1 (pre-release)

The first test version, for Linux (an AppImage). Tested on a VEVOR KI-375A
(cuts from the window: an SVG heart, cut cleanly). Expect rough edges; please
report what goes wrong in the [issues](https://github.com/cyryllo/vintyl/issues).

**Cutting**
- Send to the cutter from the window: Start and Stop, a check list before
  cutting, progress. USB printer cutters (/dev/usb/lp…, such as the VEVOR
  KI-375A) and serial ports (/dev/ttyUSB…); HPGL and DMPL.
- Knife compensation at the corners only (smooth on curves), overcut,
  inside shapes cut first, a weeding frame round the design, the knife path
  shown on the sheet. Save the cutter file (.hpgl) without cutting.
- Pen / pencil mode: draws on paper, with the stroke on, outside or inside
  the line, and fill patterns (lines, cross-hatch, waves, honeycomb and more).
- Under the port, Vintyl says when the device needs a Linux group (lp or
  dialout) and how to join it.

**Drawing**
- The sheet as you see it from the front of the cutter, the cutting width
  across, growing upwards with the design.
- Rectangle, ellipse, polygon, line, polyline, pen with curves, freehand,
  text with the system's fonts, ready shapes (star, heart, gear, ring,
  arrow and more), QR codes; open SVG files.
- Move, resize with handles, rotate, mirror, align, distribute, group,
  union / difference / intersection / exclusion, offset (with "remove the
  holes"), a pattern of small shapes inside a shape, node editing, ruler,
  grid, snapping, undo, shortcuts.
- Projects (.vintyl). Polish and English.

**Cutters**
- Choose the machine in the window; its port, connection, command language,
  axes, knife offset, overcut and speed are in its settings window (the
  button beside it). A built-in profile you change is kept as your copy
  ("Restore factory settings" brings the original back); add cutters of
  your own (~/.config/vintyl/profiles).
- Built-in profiles: VEVOR KI-375A (checked on the machine), VEVOR 870 mm
  (34 in, cuts 780 mm; said to have the KI-375A's control board, to be
  checked) and Seiki SK-870T (to be checked).
