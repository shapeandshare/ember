# Brand SVG assets

Hand-drawn vector reconstruction of the selected `../concepts/mellow-hood-v1.png` concept. These are editable paths, not embedded raster images. Minor curve differences from the generated concept are intentional cleanup.

- `mellow-light.svg`: coral body and deep plum hood/arm, for light surfaces.
- `mellow-dark.svg`: softer coral body and muted plum hood/arm, for dark surfaces. Facial features remain deep plum.
- `mellow-auto.svg`: switches between these palettes using `prefers-color-scheme`.
- `preview.html`: light, dark, and checkerboard comparison.

All three SVGs have transparent canvases and transparent negative space. They contain no background rectangle, raster data, fonts, or external dependencies. The square viewBox includes safe margins.

## Web use

For system-theme switching:

```html
<img src="/assets/brand/svg/mellow-auto.svg" alt="Mellow" width="128" height="128">
```

For an application with its own theme toggle, choose `mellow-light.svg` or `mellow-dark.svg` based on the application's current theme. Automatic mode follows the browser's preferred color scheme; it does not read a parent application's theme class. Use explicit theme files for image editors and export tools that do not support CSS media queries.

Inside each SVG, `.body`, `.accent`, and `.face` control the palette. When inlining multiple copies into HTML, give each title/description ID a unique prefix and update `aria-labelledby` accordingly.

Palette:

| Part | Light | Dark |
| --- | --- | --- |
| Body | #FF624F | #FF806B |
| Hood and arm | #591344 | #6A4764 |
| Face | #591344 | #591344 |

Suggested preview surfaces: warm cream #FFF8EB and dark plum #201922. These backgrounds are not part of the SVG assets.

## Ember and Float

`ember-light.svg`, `ember-dark.svg`, `ember-auto.svg`, `float-light.svg`, `float-dark.svg`, and `float-auto.svg` are editable vector interpretations of the selected illustrations. They use paths and SVG gradients rather than embedded images. Fine painted textures are simplified; use the PNG originals for the detailed illustration treatment.

All have transparent backgrounds. Float's translucent appearance is represented with colored gradients; its main silhouette is opaque for predictable use on different surfaces. The dark palettes mute lavender and peach highlights. Automatic versions use the same media-query behavior described above.

Ember and Float have a `0 0 1100 1050` viewBox. Preserve their aspect ratio when sizing. Each file is self-contained; when inlining multiple copies, prefix all IDs (including gradient/clip IDs) and their references to prevent collisions. Normal `<img>` usage isolates these IDs automatically.

The preview now includes all three mascots. Standalone raster illustrations and imagegen prompts are in `../mascots/`.
