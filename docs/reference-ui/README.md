# HTML UI Reference Assets

This directory is the canonical home for HTML UI reference artifacts used to implement BITOS screens.

## Expected assets

When syncing from external sources, prefer stable filenames:

- `flow-01.html`
- `flow-02.html`
- `nav-01.html`
- `nav-02.html`
- any supporting CSS/JS/image assets under `assets/`

If files are delivered with names like `html ui reference`, `html ui reference 2`, etc., copy them here and rename to the structure above so future contributors can find them quickly.

## Usage in implementation

Use these files as design references for:

- lock/home flow behavior
- sidebar navigation layout and focus states
- per-screen spacing/typography consistency

Do not serve these files in production paths; they are documentation/reference artifacts only.


## Validation command

Run `make audit-reference-ui` before starting a pixel-porting iteration.
It verifies the expected `flow-*` + `nav-*` HTML files exist in this repo checkout.
