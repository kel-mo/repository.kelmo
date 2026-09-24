# repository.kelmo

Kodi add-on repository for kel-mo's add-ons (e.g. RomM), served from GitHub Pages at
<https://kel-mo.github.io/repository.kelmo/>.

Only built zips live here. Add-on sources stay in their own (private) repositories.

## Layout

- `repository.kelmo/` – source of the repository add-on itself
- `generate.py` – builds `zips/` from add-on source dirs or prebuilt zips
- `zips/` – what GitHub Pages serves: `addons.xml`, `addons.xml.sha256`,
  `<id>/<id>-<version>.zip` with a `.sha256` each, add-on icons and `index.html` link pages
- `.github/workflows/pages.yml` – checks the sha256 files and publishes `zips/` on push to `main`

## Releasing an add-on

1. Bump the version (and `<news>`) in the add-on's `addon.xml` and commit it there.
2. `./generate.py ../plugin.program.romm` (source dir or a prebuilt zip; several allowed).
   Source checkouts ship only `git ls-files`, minus `build.py`, `README.md`, `.gitignore`, `tests/`, etc.
3. `git add zips && git commit && git push`
4. The Pages workflow publishes the site. Kodi picks up the update on its next repository check.

Old zips are kept so users can roll back; `addons.xml` lists only the newest version of each add-on.
Re-running `generate.py` without changes produces identical files.

To change the repository add-on, edit `repository.kelmo/addon.xml`, bump its version and re-run `generate.py`.

## Installing (users)

1. In Kodi, enable *Settings → System → Add-ons → Unknown sources*.
2. Download the `repository.kelmo-<version>.zip` linked at the top of <https://kel-mo.github.io/repository.kelmo/>
   (or add that URL as a file source in Kodi's file manager and browse to `repository.kelmo/`).
3. *Add-ons → Install from zip file* and pick the zip.
4. *Install from repository → kel-mo Add-on Repository* and install RomM.

## One-time GitHub setup

- Make the repository public (GitHub Pages on the free plan needs a public repository).
- *Settings → Pages → Build and deployment → Source: GitHub Actions*.

## License

GPL-2.0-or-later, see `LICENSE`. Add-ons served from `zips/` carry their own licences.
