# AI in research workshop

Static event website and printable A4 flyer for an AI in research workshop co-located with the Research Data Alliance (RDA) 27th Plenary Meeting in London. The page introduces the workshop, links to registration, and presents the venue and programme.

The site is a single HTML page with inline CSS and local image assets. No build step, package installation, or backend is required.

## Preview locally

Open `index.html` in a browser, or serve the repository directory with Python 3:

```sh
python3 -m http.server 8000
```

Then visit <http://localhost:8000>. Stop the server with `Ctrl+C`.

The page loads Normalize.css 7.0.0 and Paper CSS 0.4.1 from cdnjs, so an internet connection is needed for those stylesheets.

## Repository files

| File(s) | Purpose |
| --- | --- |
| `index.html` | Event content, registration and venue links, programme, and inline layout styles. |
| `rda_p27_satellite_event_header-small.svg` | Compressed header design displayed on the page. |
| `rda_p27_satellite_event_footer-small.svg` | Compressed footer design displayed on the page. |
| `rda_p27_satellite_event_separator.svg` | Decorative separator used beneath the header and above the footer. |
| `rda_p27_satellite_event_header.svg`, `rda_p27_satellite_event_footer.svg` | Original header and footer design variants. |
| `rda_p27_satellite_event_illustration.png` | Workshop illustration asset. |
| `icon-date.png`, `icon-place.png`, `icon-time.png` | Event detail icons. |
| `rda_logo.png`, `ukri_logo.png` | RDA and UKRI logo assets. |
| `svg_raster_optimize.py` | Resizes and recompresses PNG/JPEG images embedded in SVG files. |
| `Dockerfile`, `docker-compose.yaml` | Container environment for running the SVG optimizer. |
| `.gitignore` | Excludes macOS `.DS_Store` files. |

## Updating the site

Edit `index.html` to change the workshop description, registration URL, venue, or timetable. Layout styles are in the `<style>` element in the same file. Update the SVG artwork separately when changing information displayed in the header or footer.

Keep image paths relative to `index.html`. After editing, preview the page in a browser, check the links and images, and inspect print preview for text overflow or overlap with the footer.

## Generating the compressed header and footer

After editing the original header or footer SVG, use `svg_raster_optimize.py` to regenerate the corresponding `-small.svg` file used by the page. The script optimizes embedded PNG/JPEG images while preserving the surrounding SVG markup and vector artwork.

Run the following commands from the repository root. These examples limit embedded images to 800 × 800 pixels, preserving their aspect ratio without enlarging them, and retain their PNG/JPEG formats. Adjust the limits to balance file size and print quality; these are example settings, not a record of how the existing compressed files were produced.

### Without Docker Compose

Install Python 3.10 or later and ImageMagick 7, with the `magick` command available on your PATH. No Python packages are required. On macOS with Homebrew:

```sh
brew install python imagemagick
```

Generate both compressed files:

```sh
python3 svg_raster_optimize.py rda_p27_satellite_event_header.svg \
  --output rda_p27_satellite_event_header-small.svg \
  --max-width 800 --max-height 800

python3 svg_raster_optimize.py rda_p27_satellite_event_footer.svg \
  --output rda_p27_satellite_event_footer-small.svg \
  --max-width 800 --max-height 800
```

### With Docker Compose

Install Docker with Docker Compose and start the Docker engine. Build the optimizer image, which includes Python and ImageMagick:

```sh
docker compose build svg-raster
```

Run the same conversions through the `svg-raster` service:

```sh
docker compose run --rm svg-raster rda_p27_satellite_event_header.svg \
  --output rda_p27_satellite_event_header-small.svg \
  --max-width 800 --max-height 800

docker compose run --rm svg-raster rda_p27_satellite_event_footer.svg \
  --output rda_p27_satellite_event_footer-small.svg \
  --max-width 800 --max-height 800
```

Compose mounts the repository at `/work`, so generated files are written back to the repository. Rebuild the image after changing the script or Dockerfile.

Both workflows preserve the originals and overwrite the named compressed outputs when at least one embedded image becomes smaller. If no image becomes smaller, no output is written and any existing output is left as it was. Add `--dry-run` to either command to report potential changes without writing files. For additional lossy PNG compression, add `--png-colors 256`; `--quality` controls JPEG/WebP/AVIF quality, not PNG compression.

Review the command output, then check the page and its A4 print preview after regenerating the assets.

## Printing

The layout uses Paper CSS with an A4 sheet and two content columns. Use the browser's print dialog to print or save a PDF. Select A4 paper and check the preview; disable browser-added headers and footers if they appear.

## Hosting

Serve `index.html` and the referenced image assets from the same directory on any static web host. There is no generated output directory or deployment configuration among the tracked files.
