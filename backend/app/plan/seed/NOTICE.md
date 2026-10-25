# Licence notice for guide.json

`guide.json` is adapted from two sources. Rebuild it with `cd backend && .venv/bin/python -m scripts.build_guide_seed`.

**Text (Wikivoyage, CC BY-SA 4.0).** Sights, food spots, cuisine passages and listing descriptions come from
ru.wikivoyage.org and, where the Russian article is thin, en.wikivoyage.org (https://wikivoyage.org). They are
trimmed, paraphrased and in part machine-translated from English into Russian. Each entry links to its source
article (`source_url`). Contributors: https://ru.wikivoyage.org/wiki/Служебная:Вклад

**Photos (Wikimedia Commons).** Each photo keeps its own licence. Only CC BY, CC BY-SA, CC0 and public domain
files are used. Each `photo` object names the author (`author`), the licence (`license`) and the file page
(`file_url`, https://commons.wikimedia.org). Check the file page for the full licence terms before reuse.

**Derived data.** Dish names and notes are extracted from the cuisine passage by an LLM and are limited to dishes
named in that passage. Wikidata identifiers (`wikidata`) are kept for reference.
