# Ember brand

**Ember is the official mascot.** Its curled plum silhouette and glowing tummy
represent a warm, local source of advice. The product advises; the agent decides.

Tagline: **Give your agent a gut feeling.**

## Approved assets

| Use | Asset |
| --- | --- |
| Light-background mascot, transparent | [ember-light.svg](svg/ember-light.svg) |
| Dark-background mascot, transparent | [ember-dark.svg](svg/ember-dark.svg) |
| System-theme mascot, transparent | [ember-auto.svg](svg/ember-auto.svg) |
| Detailed illustration, cream background | [ember-v1.png](mascots/ember-v1.png) |
| README/banner, light | [hero-light.svg](hero-light.svg) |
| README/banner, dark | [hero-dark.svg](hero-dark.svg) |
| Reusable light/dark colors | [tokens.css](tokens.css) |
| Brand preview | [preview.html](preview.html) |

SVG mascots are editable gradient-based interpretations of the detailed PNG.
Keep their proportions and clear space. Both banner variants and standalone mascot SVGs have transparent backgrounds.
Choose the light or dark variant to match the surrounding surface.
Mellow, Float, and the concept sheets remain available as alternate explorations.

## Palette

| Color | Hex | Use |
| --- | --- | --- |
| Plum | `#603050` | Brand identity and light-theme links |
| Coral | `#D65E64` | Decorative warmth |
| Gold | `#FFC24D` | Inner glow and dark-theme links |
| Cream | `#FFF8EB` | Light background and dark-theme text |
| Ink | `#201922` | Dark background and light-theme text |

Secondary text: `#715568` on cream, `#D8BFCB` on ink. Keep coral and gold decorative
on light backgrounds; communicate status through text or icons as well as color.
The mascot's gradients add complementary orange and peach shades.

## Theme integration

Load `tokens.css` and use `var(--ember-surface)`, `var(--ember-text)`,
`var(--ember-muted)`, `var(--ember-accent)`, and `var(--ember-border)`.
The stylesheet defaults to system preference. Set `data-theme="light"` or
`data-theme="dark"` on the root HTML element to override it.

For GitHub README images, use a `<picture>` element with a dark-media `<source>`
and a light `<img>` fallback, as in the root README. For application-controlled
themes, select the explicit mascot variant. `ember-auto.svg` follows browser
color scheme, not arbitrary parent CSS classes.

The plugin ships copies of the two hero SVGs in
`packages/opencode-plugin/assets/` so its README works without reaching outside
the package. After editing canonical hero files here, copy both into that folder.
Do not edit the package copies independently.

Typography is system-ui; illustrations may be expressive, but product copy stays
precise and avoids promises of certainty. See [DESIGN.md](../../DESIGN.md).

## Provenance and licensing

See [the provenance guide](../../PROVENANCE.md) and [machine-readable inventory](../../provenance.json) for AI-generation disclosure, parent assets, hashes, saved prompts, license evidence, and URL-check results.
