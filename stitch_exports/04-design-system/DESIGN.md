---
name: Studio Precision
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#434655'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#824500'
  on-tertiary: '#ffffff'
  tertiary-container: '#a65900'
  on-tertiary-container: '#ffede1'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdcc3'
  tertiary-fixed-dim: '#ffb77d'
  on-tertiary-fixed: '#2f1500'
  on-tertiary-fixed-variant: '#6e3900'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Fira Sans
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Fira Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Fira Sans
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
  body-md:
    fontFamily: Fira Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Fira Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: Fira Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  code-md:
    fontFamily: Fira Code
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  code-sm:
    fontFamily: Fira Code
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin-edge: 24px
---

## Brand & Style

The design system is engineered for the high-stakes environment of database administration and migration. It prioritizes clarity, technical density, and reliability over decorative elements. The visual language is rooted in **Modern Corporate** aesthetics, utilizing a "system-first" approach that reduces cognitive load during complex schema mapping and data ETL processes. 

The emotional response should be one of control and confidence. By using a white-label inspired foundation with precise accents, the UI recedes to let the data become the primary interface. There are no gradients, no playful roundedness, and no unnecessary animations. Every pixel serves a functional purpose, facilitating long-form technical work without visual fatigue.

## Colors

The palette is strictly functional, optimized for a light-mode enterprise environment. 

- **Primary (#2563EB):** Used for critical paths, active states, and primary action buttons. It signals focus and progression.
- **Neutral/Text (#0F172A):** High-contrast slate for maximum legibility in data grids and documentation.
- **Secondary/Muted (#64748B):** Used for metadata, helper text, and inactive tab states to create visual hierarchy.
- **Accent (#D97706):** Reserved for "Warning" states, pending migrations, or high-priority technical alerts that require immediate but non-critical attention.
- **Surface & Border:** A hierarchy of grays (#F1F5F9 and #E2E8F0) is used to define containment and structure without the use of shadows.

## Typography

This design system utilizes **Fira Sans** for all UI-related communication due to its exceptional legibility and professional humanist qualities. For technical values—such as SQL snippets, connection strings, and table names—**Fira Code** is mandated to ensure character distinction (e.g., distinguishing `0` from `O`).

Typography is optimized for data density. Body text is set at 14px to allow for high information display on standard monitors. All caps labels are used sparingly for section headers within sidebars or small utility labels to differentiate from interactive text.

## Layout & Spacing

The system follows a strict **4px baseline grid** to maintain alignment in dense data environments. 

- **Layout:** A fluid grid system is used for workspace areas (query editors, mapping canvases), while a fixed 280px sidebar is used for object navigation. 
- **Density:** Padding is kept tight (8px-12px) within component containers to maximize the "above-the-fold" data visibility. 
- **Breakpoints:**
  - Desktop (1280px+): Full multi-column view with persistent navigation.
  - Tablet (768px - 1279px): Navigation collapses into an icon-only rail; content remains fluid.
  - Mobile: Not prioritized, but follows a single-column stack for monitoring dashboards only.

## Elevation & Depth

To maintain a clean, professional aesthetic, this design system avoids soft ambient shadows. Instead, it uses **Tonal Layers** and **Low-Contrast Outlines** to communicate hierarchy.

- **Level 0 (Background):** #FFFFFF. The base canvas.
- **Level 1 (Sub-surface):** #F1F5F9. Used for sidebars, header bars, and empty states.
- **Level 2 (Interactions):** Elements like cards and modals use a 1px solid border (#E2E8F0).
- **Active State:** A 2px #2563EB left-border or stroke is used to indicate the currently selected database object or active input, providing a clear "focus" anchor without needing depth.

## Shapes

A consistent **8px (0.5rem)** corner radius is applied to all primary containers, buttons, and input fields. This "Rounded" setting strikes a balance between modern software expectations and the geometric rigor required for professional tools. 

Small utility elements (tags, badges) use the same 8px radius or may scale down to 4px for very small items, but never "pill" shapes, to maintain the architectural integrity of the layout.

## Components

- **Buttons:** 
  - *Primary:* Solid #2563EB with white text. 
  - *Secondary:* 1px #E2E8F0 border, #0F172A text, white background.
  - *Ghost:* No border, #64748B text, used for secondary actions in toolbars.
- **Inputs:** 
  - Background: #FFFFFF, Border: #E2E8F0 (shifts to #2563EB on focus). 
  - Labels use `body-sm` in #0F172A.
- **Data Tables:**
  - The core of the system. Header cells use #F1F5F9 background with `label-caps`. 
  - Row height: 32px (compact) or 40px (default). 
  - Borders are horizontal-only to emphasize data flow.
- **Status Badges:** 
  - Small, rectangular with 4px radius. 
  - Success: Emerald/100 background, Emerald/700 text. 
  - Warning (Amber): #D97706 text for high-visibility alerts.
- **Code Blocks:** 
  - Background: #F1F5F9, utilizing `code-sm` typography. No syntax highlighting gradients; use distinct shades of primary blue and neutral slate for code tokens.