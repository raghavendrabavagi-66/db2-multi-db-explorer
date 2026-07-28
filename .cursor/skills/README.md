# Cursor skills (project)

## UI UX Pro Max

Installed from [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) (v2.11.0, MIT).

| Skill | Purpose |
|-------|---------|
| `ui-ux-pro-max` | Design system search, styles, colors, typography, UX guidelines |
| `ui-styling` | Tailwind / shadcn styling helpers |
| `design-system` | Design tokens, slide layouts |
| `design`, `brand`, `banner-design`, `slides` | Extended design assets (basic bundle) |

**Usage:** Ask Cursor to improve UI/UX (e.g. “redesign the Schema Compare layout for clarity”). The agent should read `ui-ux-pro-max/SKILL.md` when the task is visual or interaction design.

**Design system CLI (optional):**

```bash
python3 .cursor/skills/ui-ux-pro-max/scripts/search.py "SaaS dashboard" --design-system -p "MyApp"
```

**Update:** Re-run install from the upstream repo or `npm install -g ui-ux-pro-max-cli && uipro init --ai cursor --force` when Node.js is available.
