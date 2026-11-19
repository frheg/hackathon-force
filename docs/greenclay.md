# Green clay labels from the completion reports

`uv run python -m sketches.greenclay` (about a minute) reads every report JSON in `data/official/completion_reports/` and
writes `data/atlas/greenclay/`:

- `labels.parquet`: one row per mention of glauconite (and greensand), chlorite, nontronite, celadonite, or a green clay,
  shale, mudstone or marl ("greenish grey claystone", "olive-green mudstone"). Columns: wellbore, page, `kind`, `term`,
  `depth_from`, `depth_to`, `depth_unit`, `depth_source` (the line itself or a neighbouring line), `formation` (nearest
  name within 500 characters), `context` (`desc` rock description, `marker` a "Top Green Clay" pick, `depth_mention`,
  `text`), `confidence`, `marker`, `source_kind` (table or running text), page quality and the `snippet` it came from.
- `wells.parquet`: per wellbore, pages read, description lines read, number of mentions, kinds, and its position.
- `summary.json`: counts.

## Confidence

- **high**: a rock description with a depth that is firmly attached: an interval with a unit, a cuttings or core row whose
  first cell is the depth, or a tops-table row whose top depth follows the "Green Clay" cell.
- **medium**: a lithology word and a depth in the same sentence, or a depth on the next line.
- **low**: no depth. General text, formation descriptions, reasoning.

A mention is not presence at depth. "Slightly glauconitic" and "abundant glauconite" are both one mention.

## Numbers (19 November 2026)

5,326 report files, 648,520 pages, 4,441 wellbores. 32,586 mentions in 2,632 wellbores (59 %): glauconite 27,555,
green clay 3,171, chlorite 1,860. High confidence 6,157 labels in 912 wellbores; high or medium in 1,684. "Green Clay" as a
named marker: 1,089 mentions in 573 wellbores, 630 of them with a top depth. A spot check of 34 random high-confidence
labels found about 9 in 10 with the right mineral and the right depth (all 14 table rows right; a few running-text lines
paired the mineral with the wrong interval). Small sample: do not read it as a precision figure.

## Known weak spots

- Depths in table rows are measured depth as written, mixed units (m or ft, `depth_unit` is empty when the row did not say).
- A wide table row can carry a mineral in one cell and a depth from another.
- Few wells have a lot of description and no mention (80 with at least 20 description lines), so negatives are scarce.
- OCR errors ("glauconittic") are missed; the pattern is `glauconit\w*`.
