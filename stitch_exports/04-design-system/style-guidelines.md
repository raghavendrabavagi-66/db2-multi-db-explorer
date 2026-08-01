## Brand & Style

The design system is engineered for the high-stakes environment of database administration and migration. It prioritizes clarity, technical density, and reliability over decorative elements. The visual language is rooted in **Modern Corporate** aesthetics, utilizing a "system-first" approach that reduces cognitive load during complex schema mapping and data ETL processes. 

The emotional response should be one of control and confidence. By using a white-label inspired foundation with precise accents, the UI recedes to let the data become the primary interface. There are no gradients, no playful roundedness, and no unnecessary animations. Every pixel serves a functional purpose, facilitating long-form technical work without visual fatigue.

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