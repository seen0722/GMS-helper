# PRD: Settings Page UI/UX — Apple HIG Alignment

## Overview
Redesign the Settings page to align with Apple's Human Interface Guidelines (HIG), creating a premium, cohesive, and intuitive user experience.

## Goals
1. **Visual Consistency** — Standardize radii, spacing, and typography
2. **Interaction Delight** — Add micro-animations and haptic-like feedback
3. **Information Hierarchy** — Improve section organization with collapsible groups
4. **Accessibility** — Ensure WCAG 2.1 AA contrast ratios

---

## Requirements

### 1. Segmented Control Enhancement
| Current | Target |
|---------|--------|
| Basic button group | Apple-style with inner shadow, smooth transitions, and lift effect on active |

**Acceptance Criteria:**
- Active segment has subtle drop shadow
- 200ms spring animation on segment change
- Scale down (0.98) on press

### 2. Form Input Standardization
| Element | Current Radius | Target Radius |
|---------|---------------|---------------|
| Text inputs | Mixed (xl/lg) | `8px` uniform |
| Buttons | Mixed | `8px` for secondary, `12px` for primary |
| Cards | `12px` | Keep `12px` |

### 3. iOS-Style Toggle Switches
Replace checkboxes with native-feeling toggle switches:
- Width: 51px, Height: 31px
- Green (#34C759) when ON
- Gray (#E9E9EA) when OFF
- Animated dot transition

### 4. Typography Hierarchy
```
Section Title: 17px Semibold (text-slate-900)
Form Label: 13px Medium (text-slate-700)
Helper Text: 11px Regular (text-slate-500)
```

### 5. Collapsible Sections
- Module-Owner Mapping section should be collapsed by default
- Use `<details>/<summary>` with smooth height animation
- Chevron rotates on expand

### 6. Micro-Animations
| Action | Animation |
|--------|-----------|
| Button press | scale(0.97) for 100ms |
| Save success | Checkmark fade-in with pulse |
| Test Connection | Spinner → checkmark morph |
| Section expand | Height ease-out 300ms |

### 7. Accessibility Improvements
- Placeholder text: minimum `text-slate-500`
- Focus rings: 2px blue offset
- Keyboard navigation for all interactive elements

---

## Out of Scope
- Dark mode (future enhancement)
- Mobile-specific responsive adjustments
- Backend API changes

---

## Success Metrics
- Visual consistency score: 9/10+
- All interactive elements have feedback animations
- No WCAG AA contrast violations
