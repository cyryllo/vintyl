---
layout: default
lang: en
other_lang: pl/
wide: true
description: Vintyl is free software for vinyl cutters on Linux. Draw, open SVG and DXF files, lay them out and cut them on VEVOR, Seiki and similar cutters.
---
{% assign img = '/screenshots/' | relative_url %}

<div class="hero">
  <img src="{{ '/assets/logo.svg' | relative_url }}" alt="Vintyl logo">
  <div>
    <h1>Vintyl</h1>
    <p>Free software for vinyl cutters on Linux. Draw, lay out and cut in one window.</p>
    <p class="badges"><span>Linux</span><span>AppImage</span><span>Free &amp; open source</span><span>6 languages</span></p>
  </div>
</div>

<div class="buttons">
  <a class="button primary" href="#download">Download</a>
  <a class="button" href="{{ '/guide.html' | relative_url }}">User guide</a>
  <a class="button" href="{{ '/guide.html#s1' | relative_url }}">Installation</a>
</div>

<div class="shot"><a href="{{ img }}main-window.png"><img src="{{ img }}main-window.png" alt="Vintyl's window: a circle, a star, a text and a heart with a pattern of stars on a 780 mm cutter's sheet"></a></div>

<p class="lead">Vintyl runs the popular, inexpensive <strong>drag-knife vinyl cutters</strong> (VEVOR, Seiki and the many models built on the same control board) that come with Windows-only software such as SignMaster. Draw a design or open a file, see it on the sheet as the material lies in the cutter, check the force and speed, and cut it, straight from the window.</p>

> **Version 0.9.1, ready for use.** Tested and cutting cleanly on the
> **VEVOR KI-375A** and the **Seiki SK-870T**. Small glitches in the
> interface may still turn up: please
> [report them]({{ site.repo }}/issues/new/choose).

<div class="stats">
  <div><strong>4</strong><span>cutter profiles ready</span></div>
  <div><strong>5</strong><span>materials with their force and speed</span></div>
  <div><strong>8</strong><span>ready shapes, and QR codes</span></div>
  <div><strong>9</strong><span>fill patterns for pens</span></div>
  <div><strong>0,0</strong><span>the design to the origin in one key</span></div>
</div>

## What Vintyl can do

<div class="showcase">
  <div class="shot-col"><a href="{{ img }}knife-path.png"><img loading="lazy" src="{{ img }}knife-path.png" alt="The knife path on the sheet with the order of the cuts"></a></div>
  <div class="text-col">
    <h3>Cut cleanly with a drag knife</h3>
    <ul>
      <li>Knife compensation at the corners (smooth curves stay smooth) and an overcut, so every closed shape closes.</li>
      <li>Inside shapes are cut first: nothing comes loose before its holes are cut.</li>
      <li>A weeding frame round the design and weeding lines through the waste.</li>
      <li>The knife path on the sheet, with the order of the cuts and the travels.</li>
    </ul>
  </div>
</div>

<div class="showcase reverse">
  <div class="shot-col small"><a href="{{ img }}check-list.png"><img loading="lazy" src="{{ img }}check-list.png" alt="The check list before Start: the force and speed to set on the cutter's panel"></a></div>
  <div class="text-col">
    <h3>Materials, and a check before every cut</h3>
    <ul>
      <li>Vinyl film, heat transfer vinyl, reflective vinyl, paper and card, and your own materials, each with its force and speed for each cutter.</li>
      <li>Before Start, a short check list shows what to set on the cutter's panel, in large type, and what to check.</li>
      <li>A knife test (a square with a triangle) to set the force on a new material.</li>
      <li>Nothing goes to the cutter until you confirm.</li>
    </ul>
  </div>
</div>

<div class="showcase">
  <div class="shot-col"><a href="{{ img }}pattern-of-shapes.png"><img loading="lazy" src="{{ img }}pattern-of-shapes.png" alt="A pattern of hearts placed inside a rectangle, previewed live"></a></div>
  <div class="text-col">
    <h3>Draw and edit</h3>
    <ul>
      <li>Rectangle (with round corners), ellipse, polygon, line, polyline, pen curves, freehand and text in any installed font, also along a path.</li>
      <li>Ready shapes (star, heart, ring, arrow, gear...) and QR codes.</li>
      <li>Union, difference, intersection, exclusion, offset, node editing.</li>
      <li>A pattern of shapes: fill a shape with rows of small stars or hearts, each one whole, with a live preview.</li>
    </ul>
  </div>
</div>

<div class="showcase reverse">
  <div class="shot-col"><a href="{{ img }}pen-mode.png"><img loading="lazy" src="{{ img }}pen-mode.png" alt="Pen mode: a circle, a star and a heart filled with patterns"></a></div>
  <div class="text-col">
    <h3>Draw with a pen</h3>
    <ul>
      <li>Put a pen in the holder and switch the tool to the marker pen: no knife offset, no overcut.</li>
      <li>The stroke on, outside or inside the line, for the pen's width.</li>
      <li>Nine fill patterns: lines, cross-hatch, waves, zigzag, circles, honeycomb, diamonds, bricks, concentric.</li>
      <li>A photo as a drawing: its light and dark made of seismograph waves, a spiral or hatching.</li>
    </ul>
  </div>
</div>

<div class="showcase">
  <div class="shot-col"><a href="{{ img }}colours.png"><img loading="lazy" src="{{ img }}colours.png" alt="A design of five colours: the Colours panel and the logo, each colour in its own"></a></div>
  <div class="text-col">
    <h3>Several colours, one after another</h3>
    <ul>
      <li>An SVG of several colours opens in its colours; similar ones are merged, so one pen draws them. You see and change what goes where.</li>
      <li>The Colours panel: the order they are drawn in, a colour left out, its own pen width and fill pattern. An outline and its fill can be two pens: a black outline, a pink fill.</li>
      <li>Start goes colour after colour, with a pause to put in the next pen, or the next colour of vinyl; the origin stays, so the colours land on each other.</li>
    </ul>
  </div>
</div>

<div class="showcase reverse">
  <div class="shot-col"><a href="{{ img }}to-origin-after.png"><img loading="lazy" src="{{ img }}to-origin-after.png" alt="The design moved up to the origin with its weeding frame"></a></div>
  <div class="text-col">
    <h3>Lay it out, waste no vinyl</h3>
    <ul>
      <li>Move, resize with handles, rotate by any angle, mirror, align, distribute, group.</li>
      <li><strong>To 0,0</strong> moves the selection, or the whole design, up to the origin, with room for the frame and the knife.</li>
      <li>Copies in rows and columns, and strips for designs wider than the cutter.</li>
      <li>Open SVG and DXF files, trace a logo or a picture (PNG, JPG) into shapes to cut; save projects; undo everything.</li>
    </ul>
  </div>
</div>

## Cutters

| Cutter | Connects as | Status |
|---|---|---|
| VEVOR KI-375A (cuts 285 mm) | USB printer, HPGL | **tested**: cuts cleanly |
| Seiki SK-870T (cuts 780 mm, system 6.8H) | USB printer, HPGL | **tested**: cuts cleanly |
| VEVOR 870 mm (cuts 780 mm) | USB printer, HPGL | profile ready (the same board as the two above) |
| other VEVOR, Seiki and similar clones with the same board | USB printer, HPGL | "VEVOR / Seiki, other model": set its cutting width; it should work the same |
| other HPGL or DMPL drag-knife cutters | USB printer or serial port | add a profile of your own |

Vintyl has so far been used with these cutters in their **USB printer**
mode. Their second mode, **Virtual COM** (a serial port, another driver), is
prepared in the profiles (port, baud rate, flow control) but has not been
tried on a cutter yet. Force and speed are set on the cutter's panel: these
cutters take them from there; Vintyl shows the material's values before
Start.

<a id="download"></a>

## Download

<div class="platforms">
  <div class="platform">
    <h3>Linux <span class="tag">AppImage</span></h3>
    <p>One file with everything inside, for most Linux systems of the last years (64-bit).</p>
    <p><a class="button primary" href="{{ site.repo }}/releases/latest">Latest release</a></p>
    <p>Make it executable and start it; Vintyl offers to add itself to the applications menu. See <a href="{{ '/guide.html#s1' | relative_url }}">Installation</a>.</p>
  </div>
  <div class="platform">
    <h3>From the source</h3>
    <p>Python 3.12 or newer and Qt 6 (PySide6).</p>
    <p><a href="{{ site.repo }}#run-it-from-the-source">How to run it</a> · <a href="{{ site.repo }}/blob/main/CHANGELOG.md">What is new</a> · <a href="{{ site.repo }}/blob/main/TODO.md">Planned (in Polish)</a></p>
  </div>
</div>

## Questions

<div class="faq">
<details><summary>Does it send force and speed to the cutter?</summary>
<p>Not to these cutters: they take force and speed only from their own panel. Vintyl shows the material's values in large type before every cut, so you can set them there. The knife offset and the overcut are worked into the knife's path by Vintyl; nothing has to be set for them on the cutter.</p></details>
<details><summary>"No permission to use /dev/usb/lp0"?</summary>
<p>On Linux only the members of the device's group may send to it: join the group <code>lp</code> once (<code>sudo usermod -aG lp $USER</code>) and log in again. Help → Access to the cutter shows the commands to copy.</p></details>
<details><summary>My cutter is not on the list.</summary>
<p>If it is a VEVOR, Seiki or a similar clone with the same board, choose "VEVOR / Seiki, other model" and set its cutting width. Then please tell us how it went: Help → Diagnostic report → Report my cutter.</p></details>
</div>
