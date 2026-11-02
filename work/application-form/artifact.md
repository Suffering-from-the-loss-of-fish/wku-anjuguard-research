# WKU natural science proposal template contract

## Reference

Retained file: `/Users/wangkai/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_kulelwegv91322_e7d3/temp/RWTemp/2026-10/d577961361d6a5bbf1482721309c7c5b/1. WKU SpF(SpS) Natural Science Application Form.docx`

SHA-256: `c577c4e311f8ff371aa5b288e23efecf28c04f97ee28bfb7ed2412fcaf864095`.
One section. Three reference pages when Chinese fonts are available; the earlier two-page render omitted Chinese and is not fidelity evidence. All three corrected reference PNGs have been inspected.
Evidence: `template-render-fonts/`, `template-style-evidence.json`, `template-package-inventory.json`.

## Page system and recurring elements

A4 portrait 11906 by 16838 twips; margins top/bottom 1440 and left/right 1814 twips. Single column; line grid 312 twips. Header distance 851 twips; footer distance 992 twips. No separate first-page or odd/even option. Default header contains school crest, university name, ORSP (OGCO), and a rule. Default and even footer parts contain page-number furniture. Preserve all header, footer, section, media and relationship bytes.

## Typography and layout authority

Retain the original three centered introductory paragraphs, 14 pt Times New Roman with Chinese font declarations, 1.5 line spacing. Original Part I and Part II are bold 14 pt. Original seven questions each have an English and a Chinese paragraph at 14 pt, 1.5 line spacing, black; retain their text and run formatting. Original Normal style is 10.5 pt, justified, with no widow control. No tables, lists, footnote/endnote calls, body drawings, text boxes, controls or bookmarks occur in the reference. Header drawing is preserve-only.

New answer paragraphs use the source Normal style, with direct 12 pt Times New Roman and Songti SC, black, left alignment, exact 20 pt line spacing, 6 pt paragraph after, widow control enabled and no grid snapping. Left alignment avoids expanded mixed-language word gaps and a local renderer defect in line-final punctuation under justification. New subordinate headings use the same setting with bold and keep-with-next. References use 10.5 pt and exact 15 pt line spacing with hanging indents and keep-lines. The first render used proportional leading, which expanded the CJK font metrics excessively; exact leading preserves readable spacing. These are answer-slot formatting choices, not changes to the template styles. Do not add a cover, generic page design, header or footer.

## Slots and stable locators

All paragraph indices below are zero-based direct `w:body/w:p` positions in the retained `word/document.xml`, before insertion.

- P0–P2 introduction: preserve text/runs. Keep consecutive lines together.
- P3, P6 blank answer/title space: P3 may be reduced to a short blank spacer; P6 becomes the English research title.
- P4 English title field label: preserve. P5 Chinese placeholder is the title-answer slot; replace with the specific Chinese title and remove placeholder underlining.
- P7 Part I: preserve and keep with the following question.
- P8/P9: preserve English/Chinese section 1. P10 becomes context, related work, scope and bibliography.
- P11/P12: preserve section 2. P13 becomes research contents, objectives, hypotheses and scientific questions.
- P14/P15: preserve section 3. P16 becomes method, data, fair comparisons, measures, analysis and feasibility.
- P17/P18: preserve section 4. P19 becomes three bounded candidate contributions with validation conditions.
- P20/P21: preserve section 5. P22 becomes relative 12-month schedule, planned outcomes, academic exchange and adjustment criteria.
- P23 Part II: preserve; start on a new page for readability.
- P24/P25: preserve section II.1. P26 becomes verified code basis and research evidence limitations.
- P27/P28: preserve section II.2. P29 becomes available materials, missing resources and proposed remedies.

Capacity: answer areas expand across pages; the template states no word/page limit. Use paragraph keep rules and selective page breaks to prevent detached bilingual prompts. Disable hanging punctuation in new answer paragraphs because the renderer omits some line-final punctuation. Keep the seven sections in original order. No unsupported names, student IDs, advisor approval, actual funding, awards, data collection or real-model results may be invented.

## Package preservation and fidelity gates

Full 23-part inventory in `template-package-inventory.json`. Only `word/document.xml` is editable. Preserve all other package parts byte-for-byte, including styles, theme, numbering, footnotes/endnotes, settings, opaque customXml, metadata, header/footer/media and relationships. New references use visible source URLs without new relationship parts.

Render with the existing project `work/research-package/fonts.conf`; without it the local renderer drops Chinese glyphs. Inspect every final PNG. Audit full paragraph-text coverage against authored content and PDF extraction; verify source SHA, all 22 other parts unchanged, all seven bilingual prompt pairs retained, no placeholder residue, no overlap/clipping or blank pages. Final deliverable only: `/Users/wangkai/Desktop/温肯科研/科研申请书.docx`.
