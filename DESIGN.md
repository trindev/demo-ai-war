---
name: แยกถูก รับถึงบ้าน
description: A pickup is a book of coupons; each stage is stamped when done and never removed.
colors:
  carrier-green: "#0b5d3b"
  carrier-green-dark: "#084a2f"
  carrier-green-deep: "#063a25"
  carrier-green-soft: "#d9eadf"
  carrier-green-tint: "#eef5f0"
  carbon-purple: "#4b3f72"
  carbon-purple-soft: "#ebe8f3"
  stamp-red: "#c8102e"
  ink: "#18202a"
  ink-muted: "#55606a"
  field-grey: "#7a858e"
  hairline: "#c9d0ca"
  table: "#e9ede8"
  coupon-stock: "#ffffff"
  tab-head: "#e4e8e3"
  ai-soft: "#e7e9ee"
  warn: "#7d5200"
  warn-soft: "#fbefc9"
  danger: "#b00020"
  danger-soft: "#fbe3e6"
  info: "#1f4f8f"
  info-soft: "#dfe9f6"
  mat-pet: "#2f6fde"
  mat-hdpe: "#2ba3c9"
  mat-other-plastic: "#7a6fd6"
  mat-cardboard: "#a8601a"
  mat-paper: "#d2a514"
  mat-aluminum: "#6f7c8a"
  mat-steel: "#33404d"
  mat-glass: "#1f9a8a"
  night-table: "#10161d"
  night-stock: "#18212b"
  night-surface: "#1f2a36"
  night-tab-head: "#232f3c"
  night-shell: "#0b1016"
  night-ink: "#e8edf2"
  night-ink-muted: "#a3b0bd"
  night-hairline: "#2f3c4a"
  night-rule: "#5d6f83"
  night-field: "#6f8196"
  night-carrier-green: "#1f7a52"
  night-green-text: "#7fd6aa"
  night-lavender: "#c7bdf0"
  night-series: "#a99be8"
  night-stamp: "#ff7a8a"
  night-ink-plate: "#dfe5ec"
  night-warn: "#f2c14e"
  night-danger: "#ff8f9b"
  night-info: "#9cc2f5"
typography:
  display:
    fontFamily: "Athiti, Anuphan, Noto Sans Thai, Leelawadee UI, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 700
    lineHeight: 1.3
  headline:
    fontFamily: "Athiti, Anuphan, Noto Sans Thai, Leelawadee UI, sans-serif"
    fontSize: "1.12rem"
    fontWeight: 700
    lineHeight: 1.35
  title:
    fontFamily: "Athiti, Anuphan, Noto Sans Thai, Leelawadee UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Anuphan, Noto Sans Thai, Thonburi, Leelawadee UI, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Anuphan, Noto Sans Thai, Thonburi, Leelawadee UI, system-ui, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    lineHeight: 1.35
  figure:
    fontFamily: "Athiti, Anuphan, Noto Sans Thai, Leelawadee UI, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 700
    lineHeight: 1.2
    fontFeature: "tnum"
  figure-lg:
    fontFamily: "Athiti, Anuphan, Noto Sans Thai, Leelawadee UI, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 700
    lineHeight: 1.15
    fontFeature: "tnum"
  button:
    fontFamily: "Athiti, Anuphan, Noto Sans Thai, Leelawadee UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.35
rounded:
  none: "0"
  sm: "2px"
  md: "3px"
spacing:
  tight: "0.5rem"
  stack: "0.9rem"
  page: "1rem"
  coupon: "1.05rem"
components:
  button-primary:
    backgroundColor: "{colors.carrier-green}"
    textColor: "{colors.coupon-stock}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "0.55rem 1.05rem"
  button-primary-hover:
    backgroundColor: "{colors.carrier-green-dark}"
  button-primary-active:
    backgroundColor: "{colors.carrier-green-deep}"
  button-primary-lg:
    backgroundColor: "{colors.carrier-green}"
    textColor: "{colors.coupon-stock}"
    rounded: "{rounded.md}"
    padding: "0.8rem 1rem"
    width: "100%"
  button-ghost:
    backgroundColor: "{colors.coupon-stock}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "0.55rem 1.05rem"
  button-ghost-hover:
    backgroundColor: "{colors.tab-head}"
  button-disabled:
    backgroundColor: "{colors.tab-head}"
    textColor: "{colors.ink-muted}"
  coupon:
    backgroundColor: "{colors.coupon-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "{spacing.coupon}"
  coupon-head:
    backgroundColor: "{colors.tab-head}"
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
    padding: "0.5rem 1.05rem"
  step-box:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.coupon-stock}"
    typography: "{typography.figure}"
    width: "2.6rem"
  bag-code:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.coupon-stock}"
    rounded: "{rounded.sm}"
    height: "2.1rem"
    padding: "0 0.5rem"
  slot-flag:
    backgroundColor: "{colors.carrier-green}"
    textColor: "{colors.coupon-stock}"
    padding: "0 0.9rem"
  figure-cell:
    backgroundColor: "{colors.coupon-stock}"
    textColor: "{colors.carbon-purple}"
    typography: "{typography.figure}"
    padding: "0.4rem 0.7rem 0.45rem"
  stamp:
    textColor: "{colors.carrier-green}"
    rounded: "{rounded.md}"
    padding: "0.05rem 0.6rem"
  stamp-void:
    textColor: "{colors.stamp-red}"
  badge:
    backgroundColor: "{colors.carrier-green-tint}"
    textColor: "{colors.carrier-green-dark}"
    rounded: "{rounded.sm}"
    padding: "0.08rem 0.45rem"
  input:
    backgroundColor: "{colors.coupon-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.65rem"
  input-number:
    textColor: "{colors.carbon-purple}"
  segment-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.coupon-stock}"
  cover-band:
    backgroundColor: "{colors.carrier-green}"
    textColor: "{colors.coupon-stock}"
    rounded: "{rounded.md}"
    padding: "1rem 1.1rem"
---

# Design System: แยกถูก รับถึงบ้าน

## Overview

**Creative North Star: "The Coupon Book"**

A pickup is a book of coupons: request, verify, weigh, deliver. Each coupon is a sheet of white stock lying on a cool grey-green table, framed in navy-black ink, with a tabbed head, hairline inner rules, and dashed perforations between its stubs. When a stage is done it is stamped; passed stages are struck through and stay where they are. Nothing floats, nothing is pill-shaped, nothing glows.

Three inks do the work. Carrier green is the service itself: the top rule of the shell, the cover band, the primary button, the slot flag, the "done" stamp. Carbon purple is the colour of anything that was filled in: every counted, weighed or priced figure, on every page. Navy-black ink draws the frames and fills the solid boxes that carry step numbers and bag codes. Red appears only where something was voided, went wrong, or cannot be recycled.

The admin back office is the same book on the night shift: dark stock, lighter rules, lavender figures. It is produced by redefining the tokens on the admin body, so every component is shared between the two themes.

**Key Characteristics:**
- Ruled frames in ink (1.5px), hairline inner rules (1px), dashed perforations between stubs.
- Tab heads sit flush against the top edge of a coupon; step numbers are solid ink boxes flush left.
- Figures are Athiti 700 in carbon purple with tabular numerals; their small label sits above them.
- Corners are almost square (3px and 2px). Coupons carry no shadow.
- Stage stubs that stamp: one tilted stamp on the current stage, landing once when the stage changes.
- All interface text is Thai, set in Athiti (heads, figures, buttons) and Anuphan (reading text).

## Colors

A printed-form palette: white stock, one service green, one carbon-copy purple for figures, ink for structure, red held back for stamps and faults.

### Primary
- **Carrier Green** (#0b5d3b): the service. Top rule of the shell (3px), cover band, primary button, slot flag on a request coupon, the "next stop" sequence box, the green stamp, form accent and caret colour. Dark (#084a2f) is its hover and its link/text form; deep (#063a25) is the pressed state, the primary button's border and the partner cover band.
- **Carrier Green Soft / Tint** (#d9eadf / #eef5f0): hover and resting fill of the photo dropzone, scanner box, active phone tab, table row hover, the positive notice, and the one accented figure cell.

### Secondary
- **Carbon Purple** (#4b3f72): every filled-in figure: points, bag counts, kilograms, prices, table number columns, chart series, the pickup code, number inputs as typed. Also the focus outline (3px, 2px offset) and text selection.
- **Carbon Purple Soft** (#ebe8f3): the selected price cell, held with a 2.5px inset purple frame.

### Tertiary
- **Stamp Red** (#c8102e): the void stamp, the non-recyclable material swatch, and the map pin of a request that could not be routed.
- **Danger** (#b00020 on #fbe3e6), **Warn** (#7d5200 on #fbefc9), **Info** (#1f4f8f on #dfe9f6): status badges and notices only, always as a 1px framed box in its own colour.
- **Material swatches**: eight fixed colours (PET, HDPE, other plastic, cardboard, paper, aluminium, steel, glass) plus Stamp Red for non-recyclable, drawn as a small upright bar (0.5rem by 0.95rem), never as a round dot.

### Neutral
- **Ink** (#18202a): text, the 1.5px frame of every coupon, solid ink boxes (step number, bag code, active segment, active time slot), the price ticker, toast and chart tooltip, the driver cover band.
- **Ink Muted** (#55606a): secondary text and the small labels above figures.
- **Field Grey** (#7a858e): input borders at rest, the strike through a passed stage, sparkline strokes, placeholders. A drawing colour, not a reading colour.
- **Hairline** (#c9d0ca): 1px inner rules inside a coupon and table cell borders.
- **Table** (#e9ede8): the page behind the coupons.
- **Coupon Stock** (#ffffff): coupons, inputs, the shell bars.
- **Tab Head** (#e4e8e3): coupon heads, table headers, ghost-button hover, the disabled button.

### Night shift (admin)
The admin body redefines the same roles: table #10161d, stock #18212b, surface #1f2a36, tab head #232f3c, shell #0b1016, ink #e8edf2, muted #a3b0bd, hairline #2f3c4a, rule #5d6f83, field #6f8196, carrier green #1f7a52 with #7fd6aa as its text form, figures in lavender #c7bdf0, chart series #a99be8, stamp #ff7a8a. Soft fills become translucent washes of their hue (12 to 26 percent). Solid ink boxes flip to a light plate (#dfe5ec) with dark text so step numbers and bag codes stay legible on dark stock. The QR always sits on white.

### Named Rules
**The Filled-In Figure Rule.** A number that was counted, weighed, priced or scored is carbon purple (lavender at night), Athiti 700, tabular. Purple is never used for a heading, a button or a decoration; if it is purple, somebody measured it. The one sanctioned second ink for a figure is carrier green dark, used to keep the second account apart in the two-account carbon ledger and on the one accented cell.

**The Stamp Red Rule.** Red marks a void, an error, a non-recyclable item or an unroutable stop. It is never a button fill, a brand accent or an emphasis colour.

**The Night Shift Rule.** Admin dark is a token swap on the body, nothing more. A new component is written once against the tokens and must read in both themes; solid ink boxes are the only elements with an explicit night override.

## Typography

**Display Font:** Athiti (with Anuphan, Noto Sans Thai, Leelawadee UI, sans-serif)
**Body Font:** Anuphan (with Noto Sans Thai, Thonburi, Leelawadee UI, system-ui, sans-serif)
**Label/Mono Font:** none distinct; labels are Anuphan. A system monospace stack appears only in admin code blocks.

**Character:** Athiti is a looped-and-loopless hybrid with a printed-ticket firmness, used at weights 600 to 700 for anything that reads like form printing: heads, figures, stamps, buttons. Anuphan carries the reading text at 400 to 600 with a 1.55 line height that gives Thai vowel and tone marks room.

### Hierarchy
- **Display** (Athiti 700, 1.6rem, 1.3): page titles and the name on the cover band (1.5rem there).
- **Headline** (Athiti 700, 1.12rem, 1.35): coupon tab heads.
- **Title** (Athiti 700, 1rem, 1.35): sub-heads inside a coupon; widget heads on the dashboard.
- **Body** (Anuphan 400, 1rem, 1.55): reading text. Helper text is 0.9rem in Ink Muted; explanatory paragraphs cap at 70 to 75ch.
- **Label** (Anuphan 600 to 700, 0.76 to 0.84rem, 1.35, sentence case): the caption above a figure, table headers, form labels. No uppercase, no letter-spacing.
- **Figure** (Athiti 700, tabular numerals, carbon purple): 1.35rem in coupon field cells and totals, 1.55rem in ledger cells, 1.7 to 1.9rem for ledger and points, 2.5 to 2.6rem for the one headline number of a panel.
- **Code** (Athiti 700, 1.45rem, letter-spacing 0.16em, carbon purple): the six-character pickup code under the QR. Bag codes use Athiti 700 at 1.02rem with 0.03em tracking.

### Named Rules
**The Label-Over-Figure Rule.** A figure cell is a small muted label above a large purple number, like a printed field with its entry written in. In markup the number comes first and the cell is reversed in layout, so assistive tech reads the value before its caption.

**The Tabular Rule.** Anything numeric that can change or be compared (figures, table number columns, time slots, coordinates, deltas) uses tabular numerals, and table number columns are right-aligned.

## Layout

Single column, three widths: narrow (580px) for member and driver, mid (920px) for settings, carbon and the partner portal, wide (1440px) for dispatch, prices and records. Page padding is 1rem; coupons stack 0.9rem apart; a coupon's inner padding is 1.05rem. There is no spacing token set in the stylesheet: these are the reused literals, alongside 0.5rem for tight gaps.

Phone first. Below 900px the navigation is a fixed bottom bar (64px plus the safe-area inset) with an equal column per page, dashed separators and a 4px green top edge on the active tab; from 900px it moves into the top bar as flat tabs whose active one is filled green. The admin, from 900px, gets a fixed 236px left rail instead, with the brand over a 3px green rule and ruled menu rows.

Numbers that belong together share one frame rather than sitting in separate boxes: a grid with a single outer ink border and shared inner rules (two columns on a phone, auto-fit columns on wider screens). The dispatch page pairs a sticky map with a 410px side column from 960px; the price page pairs a 430px cell grid with the detail coupon from 980px.

On phones (below 640px), each table row becomes a stacked list of "column name, value" pairs, so no figure is cut by the frame and nothing scrolls sideways. `labelTables` in `web/portal.js` copies each column name onto its cells for this.

## Elevation & Depth

Flat. Coupons, cells, buttons and inputs have no shadow; depth is drawn with line weight (1.5px frame, 1px hairline, 2px dashed perforation) and with the tab-head tone against white stock. A shadow means only one thing: this element is physically above the page or the map.

### Shadow Vocabulary
- **Float** (`0 10px 28px rgba(24, 32, 42, .18)`; night `0 12px 30px rgba(0, 0, 0, .5)`): toast, chart tooltip, and the navigation header and recentre button that sit over the driver's map.
- **Sheet edge** (`0 -8px 24px rgba(24, 32, 42, .14)`): the bottom sheet of the driver's navigation mode.
- **Map pin** (`0 2px 6px rgba(0, 0, 0, .35)`): pins on map tiles, with a 2.5px white ring.

### Named Rules
**The Flat Stock Rule.** Nothing that lies on the table casts a shadow. If an element is not floating over a map or over the page, it gets a ruled frame instead.

## Shapes

Near-square corners: 3px on coupons, buttons, stamps and the cover band; 2px on inputs, badges, chips, bag codes and inner frames; 0 on cells that share a border. There are no pills. Circles are reserved for things that are round in the world: map pins, the vehicle marker, the loading spinner. The logo mark keeps its own 5-unit corner.

Lines carry meaning by style. A solid 1.5px ink line is a frame. A solid 1px hairline separates fields within one coupon. A dashed line is a perforation or a place not yet filled: between stage stubs, between the cover band and the points stub, above the QR stub, between the two carbon accounts, around the photo dropzone and the scanner, and on anything voided or switched off (a missing bag chip, a completed stop's sequence box, a skipped bag).

Stamps are the one tilted shape: a 3px frame in its own colour, rotated 5 to 6 degrees counter-clockwise (3 degrees and a 2px frame when small inside a table).

### Named Rules
**The Perforation Rule.** Dashes are for tear lines and unfilled or voided things. Do not use a dashed border as general decoration, and do not separate two stubs of one coupon with a solid gap or a margin.

## Components

### Buttons
Printed, firm, square.
- **Shape:** near-square (3px), 1.5px border, Athiti 700 at 1rem, padding 0.55rem by 1.05rem. Small is 0.32rem by 0.7rem at 0.9rem; large is 0.8rem by 1rem at 1.15rem.
- **Primary:** carrier green fill, white text, deep-green border. One per coupon; the request flow ends in a full-width large primary.
- **Hover / Focus:** hover darkens to carrier green dark, press to deep (0.15s colour transition, no movement). Focus is the global 3px carbon-purple outline at 2px offset.
- **Ghost:** stock fill, ink text, ink border; hover fills with the tab-head tone.
- **Disabled:** tab-head fill, muted text, hairline border.
- **Segmented control:** an ink-framed strip of text buttons divided by 1px ink lines; the active segment is a solid ink box.

### Chips
- **Status badge:** a 1px framed rectangle (2px corners) in its own colour over its soft tint, 0.76rem bold. The AI badge is a solid ink box. Never a pill.
- **Bag chip:** an ink-framed chip whose leading cell is a solid ink box holding the bag code (for example 21-A); verified turns the box green, missing strikes the text through and dashes the frame.
- **Suggestion chip:** dashed field-grey frame that turns solid ink on hover.

### Cards / Containers
- **Corner Style:** 3px.
- **Background:** coupon stock on the table tone.
- **Shadow Strategy:** none (see Flat Stock Rule).
- **Border:** 1.5px ink. The current driver stop thickens to 2.5px carrier green.
- **Internal Padding:** 1.05rem; the tab head bleeds to the frame with 0.5rem by 1.05rem padding, tab-head fill and a 1.5px ink rule beneath.
- **Numbered step head:** a solid ink box (2.6rem wide, Athiti 700 at 1.35rem) flush to the left edge of the tab head, then the head and one helper line.
- **Cover band:** a solid colour band in an ink frame holding the holder's name: carrier green for a member, ink for a driver, deep green for a partner. The member's points sit in a white stub on the right, behind a 2px dashed perforation.

### Inputs / Fields
- **Style:** stock fill, 1.5px field-grey border, 2px corners; border turns ink on hover. Number inputs set their value in carbon purple at weight 600 with tabular numerals.
- **Focus:** the global 3px carbon-purple outline.
- **Stepper:** minus, value, plus in one field-grey frame; the buttons are tab-head cells.
- **Time slots:** a two-column grid of framed Athiti buttons; the chosen one becomes a solid ink box.
- **Switch:** a square-cornered track with a rectangular thumb that slides 1.1rem and turns green.
- **Dropzone:** 2px dashed ink frame on green tint with a line icon in carrier green.

### Navigation
- **Phone:** fixed bottom bar, equal columns, 22px line icon over a 0.78rem label, dashed separators; active tab has ink text, a 4px green top edge and a green-tint fill.
- **Desktop:** tabs inline in the top bar under its 3px green rule; active tab is solid green with white text.
- **Admin desktop:** 236px fixed left rail on the night shell, ruled rows, active row solid green.
- Icons are 1.8px stroked line drawings in the current text colour.

### Request coupon with stage stubs (signature)
One coupon per pickup request. Head: request number in Athiti on the tab-head tone, with the time slot as a green flag at the right end. Below it four numbered stage stubs across, divided by 2px dashed perforations. A passed stage is struck through corner to corner with a field-grey line and keeps its place. The current stage carries one stamp: green 3px frame, Athiti 700, tilted 6 degrees, overlapping the stub's lower edge. Then a three-cell field row (label over purple figure), the bag chips, and behind a 2px dashed tear line the QR stub with the spaced purple code.

Motion: the stamp lands once when a stage changes (0.45s, `cubic-bezier(.16, 1, .3, 1)`, from 1.8 scale, minus 12 degrees and transparent). It does not replay on refresh and is removed under reduced motion. The same landing is used for the confirmation stamp after a request is sent.

### Figure ledger
A grid of label-over-figure cells inside one ink frame with shared rules. The two-account carbon ledger is the special case: exactly two cells divided by a 2px dashed perforation (stacking with a horizontal perforation under 520px), first figure purple, second carrier green dark. The two accounts are never summed.

### Tables
Ink-framed, tab-head header row with a 1.5px ink rule under it, hairlines between rows and between columns, number columns right-aligned in purple, row hover in green tint.

## Do's and Don'ts

### Do:
- **Do** build every new surface as a coupon: 1.5px ink frame, 3px corners, a tab head flush to the top edge, no shadow.
- **Do** set every measured number in Athiti 700, carbon purple, tabular, with its muted label above it.
- **Do** put related figures in one shared frame with inner rules rather than in separate boxes.
- **Do** use a 2px dashed line wherever two stubs of one coupon meet, and for anything unfilled or voided.
- **Do** show completion with a stamp: one per coupon, tilted, in carrier green; red only for a void.
- **Do** keep passed stages visible and struck through; a finished step is never removed.
- **Do** write components against the tokens so they read on both day stock and the admin night shift.
- **Do** keep the two carbon figures side by side and separate.
- **Do** disable the stamp landing under reduced motion.

### Don't:
- **Don't** use rounded cards, pill badges or soft drop shadows; this system replaced exactly that look.
- **Don't** put a shadow on anything that is not floating over a map or the page.
- **Don't** use carbon purple for headings, buttons or decoration.
- **Don't** use red as an accent or a button colour.
- **Don't** place a small label line above a heading; the role is already stated in the top bar and the cover band's second line.
- **Don't** set figures in Anuphan or in proportional numerals.
- **Don't** use field grey for reading text.
- **Don't** add a second stamp to a coupon or replay the landing on refresh.
- **Don't** draw material swatches as round dots or invent new material colours per page.
