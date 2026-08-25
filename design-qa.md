# Design QA

## Comparison target

- Source visual truth: supplied visual reference (kept outside this repository)
- Implementation capture: `artifacts/ui-implementation-1536x1024-v7.png`
- Side-by-side evidence (source left, implementation right): `artifacts/design-comparison-3072x1024-v7.png`
- Viewport/state: 1536 × 1024 px, desktop, light theme, populated demo state matching the supplied mock.
- Density normalization: both captures are 1536 × 1024 px at Qt offscreen scale 1; no resampling was used.

## Findings

No actionable P0, P1, or P2 differences remain in the matched demo state.

- [P3] Window-control glyphs follow the host platform in the macOS offscreen capture rather than the reference's white Windows glyphs. The release target is Windows, and the implementation provides functioning minimize, maximize, and close controls; the brief expressly permits OS-default title-bar controls.
- [P3] The report detail says CSV rather than `HTML/CSV`. This reflects the shipped CSV-only report path, which satisfies the requirement to support CSV *or* HTML and avoids exposing a control for an unavailable format.

## Required fidelity surfaces

- Fonts and typography: uses `Segoe UI` with `Malgun Gothic` fallback; hierarchy and Korean labels remain legible without wrapping in the reference-sized capture. Host font rasterization differs slightly from the supplied Windows capture.
- Spacing and layout rhythm: title band, two-column top area, four middle panels, and bottom three-column preview use the same 1536 px composition; panel widths, vertical landmarks, row heights, and preview placement were adjusted against the side-by-side image.
- Colors and visual tokens: blue primary header/actions, white and `#F8FAFC` surfaces, muted borders, green/blue/orange badges, and red/blue summary totals match the intended semantic palette.
- Image quality and asset fidelity: the title shield is an exact crop of the supplied shield asset at `resources/icons/title-shield.png`; no inline SVG, CSS art, or placeholder was used. Remaining interface icons are platform-native controls.
- Copy and content: the 11 detection labels, masking wording, options, summaries, history, and preview labels match the Korean brief. Demo row values mirror the reference only in `--demo` mode; the normal app starts empty.

## Focused comparison evidence

- Header/title region: checked the shield crop, title, version, primary actions, and title-bar controls in the combined capture.
- Dense-grid region: checked file-list columns, execution summary alignment, four middle panels, history rows, preview columns, badge colors, and note/button placement in the combined capture.

## Comparison history

1. Initial capture `ui-implementation-1536x1024-v2.png` exposed P1 title-icon rendering and P2 differences in the middle-panel columns, ordering, badge colors, file metadata, and summary scrollbar.
2. Replaced the unstable host shield with the supplied shield asset; aligned the title palette, middle panel widths/order, status coloring, demo metadata, badges, and summary overflow.
3. Final capture `ui-implementation-1536x1024-v7.png` confirms the corrected composition in the same viewport and state after the final functional changes.

## Implementation checklist

- [x] Source and rendered captures opened together and compared.
- [x] Primary file selection, masking controls, analysis, preview, and de-identification paths are interactive.
- [x] Final design capture retained with the project.

final result: passed
