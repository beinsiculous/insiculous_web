# Theme images

| file | used by | credit / licence |
|---|---|---|
| `fort-knight.jpg` | `themes.css` (FortKnight background) | Generated composite (PIL, 2400×1350): on the left, a photo by [Miryam León](https://unsplash.com/@miryam_leon) on [Unsplash](https://unsplash.com/photos/BwITbaWSPjk); on the right, a photo by Evija Martina on Unsplash — both Unsplash License, feathered into a dark center |
| `fork-knife.jpg` | `themes.css` (ForkKnife background: a dark flat-lay — cleaver, carving fork, garlic and herbs around a board — with the content column placed on the sheet of kraft paper at its centre) | Photo by [Sergey Kotenev](https://unsplash.com/@sergeykotenev) on [Unsplash](https://unsplash.com/photos/3qUIzLtMNkw) (Unsplash License), re-encoded at 2000 px, JPEG q80. If the file is missing the theme shows its flat `--background` |

These are served from `public/`, so `themes.css` (beside them at `public/app/shared/`) references them as `url(../images/<file>)`.
