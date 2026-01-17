# GAP Analysis: Settings Page — Apple HIG Alignment

## Summary
This document identifies specific gaps between the current Settings page implementation and Apple HIG standards.

---

## Gap Matrix

| # | Category | Current State | Apple HIG Standard | Gap Level | Fix Priority |
|---|----------|---------------|-------------------|-----------|--------------|
| 1 | **Border Radii** | Mixed: `rounded-xl` (12px), `rounded-lg` (8px) | Consistent 8px for inputs, 12px for cards | Medium | P1 |
| 2 | **Segmented Control** | Basic button group, no shadow on active | Inner shadow, spring animation, scale feedback | High | P1 |
| 3 | **Toggle Switches** | HTML checkboxes | iOS-style toggle (51x31px, green/gray) | High | P1 |
| 4 | **Typography** | Section headers same weight as content | Clear hierarchy: 17px Semibold / 13px Medium / 11px Regular | Medium | P2 |
| 5 | **Placeholder Contrast** | `text-slate-400` (~#94a3b8) | Minimum `text-slate-500` for AA compliance | Low | P2 |
| 6 | **Button Feedback** | No press animation | Scale 0.97 on active, spring transition | Medium | P2 |
| 7 | **Collapsible Sections** | All sections expanded, dense layout | `<details>` with chevron rotation, collapsed by default | Medium | P2 |
| 8 | **Success Feedback** | Text-only status messages | Animated checkmark, subtle pulse | Low | P3 |
| 9 | **Focus States** | Basic browser focus | 2px blue ring with 2px offset | Low | P2 |
| 10 | **Card Shadow** | `shadow-sm` | Apple's softer multi-layer shadow | Low | P3 |

---

## Files to Modify

### Primary
| File | Changes |
|------|---------|
| `backend/static/index.html` | Update CSS classes, add toggle HTML structure |

### CSS Changes (inline in `<style>`)
```css
/* Lines ~78-96: Segmented control styles */
/* Lines ~204-210: Button press states */
/* New: iOS toggle styles */
/* New: Collapsible section animations */
```

---

## Implementation Order

### Phase 1 — High Impact (P1)
1. Standardize all input border-radius to `rounded-lg`
2. Enhance segmented control CSS
3. Implement iOS toggle switches

### Phase 2 — Polish (P2)
4. Typography hierarchy adjustments
5. Placeholder contrast fix
6. Button micro-animations
7. Collapsible sections for Module-Owner

### Phase 3 — Refinement (P3)
8. Success feedback animations
9. Enhanced focus states
10. Card shadow refinement

---

## Estimated LOC Changes
- CSS additions: ~80 lines
- HTML structure updates: ~50 lines
- Total: ~130 lines
