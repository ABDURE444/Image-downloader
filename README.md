# Website Photo Downloader

Give it one or more web page links. It downloads the photos on those pages
(JPG, JPEG, PNG, WebP), prefers the full-size originals, skips icons, logos,
separators and tracking pixels, removes duplicates, sorts the photos into one
folder per page, writes a `README.txt` (source page of every image plus the
total count) and packs everything into a single ZIP file.

**Requirements:** Python 3.9 or newer and an internet connection. No extra
packages are needed.

## Quick start

### 1. Put your page links inside the Python file

Open `website_photo_downloader.py` in Notepad (or any text editor). Near the
top you will find this box:

```python
URLS = [
    "PASTE_PAGE_LINK_1_HERE",
    "PASTE_PAGE_LINK_2_HERE",
    "PASTE_PAGE_LINK_3_HERE",
    "PASTE_PAGE_LINK_4_HERE",
    "PASTE_PAGE_LINK_5_HERE",
]
ZIP_NAME = ""
```

Replace each `PASTE_...` text with a full page address copied from your
browser:

```python
URLS = [
    "https://www.mysite.com/",
    "https://www.mysite.com/about.html",
    "https://www.mysite.com/gallery.html",
]
```

Rules for the list:

- Keep the **quotes** `" "` around every link and the **comma** `,` after it.
- Use plain straight quotes `"`. Curly quotes pasted from Word or chat apps
  break the script.
- Keep the `[` at the start and the `]` at the end.
- Add as many links as you like (copy a line and change the link). Lines that
  still say `PASTE_...` are ignored.
- Optional: type a name in `ZIP_NAME = ""` (for example `"my_photos"`) to
  choose the ZIP name. If left empty, the ZIP is named after the website.

Save the file.

### 2. Open a terminal in the folder

On Windows: open the folder in File Explorer, click the address bar, type
`powershell` and press Enter. (PowerShell and CMD both work.)

### 3. Run it

```
python website_photo_downloader.py
```

If `python` is not recognised on Windows, use `py website_photo_downloader.py`.
On Mac/Linux use `python3 website_photo_downloader.py`.

### 4. Get your ZIP

When it finishes, it prints a summary:

```
Unique photos downloaded : 14
Pages that failed        : 0
ZIP file                 : <your folder>\mysite_com_photos.zip
```

The ZIP is created in the folder you ran the command from. Inside it: one
folder per page plus `README.txt`.

To use it for another website, replace the links in `URLS`, save, and run
again.

## Other ways to give links (optional)

These override the `URLS` list:

```
python website_photo_downloader.py https://site.com https://site.com/about
python website_photo_downloader.py -f pages.txt
```

(`pages.txt` has one link per line.) If the `URLS` list is empty or untouched
and no links are given, the script asks you to paste them in the window.

## Options

Add these at the end of the command:

| Option | Meaning |
|---|---|
| `-o NAME` | Name of the ZIP/folder |
| `-f FILE` | Read links from a text file |
| `--min-kb N` | Ignore images smaller than N KB (default 15). Try `--min-kb 5` to catch small photos, or `--min-kb 50` to skip more thumbnails |
| `--logos` | Also keep logos |
| `--same-site-only` | Only keep images hosted on the same website as the page |
| `--keep-folder` | Keep the unzipped folder next to the ZIP |

## Limits

- It reads only the exact pages you list. It does not crawl a whole site, so
  list every page you want.
- It reads the page's source code, so images that appear only after
  JavaScript runs (some modern shops, social media) cannot be found.
- Very long lists take time (everything is downloaded one by one), and some
  sites may block many fast requests. If that happens, use smaller batches.

## Troubleshooting

- **0 photos or very few:** try `--min-kb 1`. If the site builds its pages with
  JavaScript, this tool will not see those images.
- **"Could not open page" / 403 / 404:** check the link opens in your browser.
  Some sites block automatic downloads, and this tool does not bypass that.
- **It asks me to paste links although I edited the file:** make sure you
  saved the file, every link is inside quotes with a comma after it, and you
  replaced the `PASTE_...` text.
- **I pasted the script into the Python `>>>` prompt:** type `exit()`, press
  Enter, and run the file as shown above.

## Responsible use

Photos on websites usually belong to their owners. Only download and use
images where you have permission (your own site, with the owner's consent, or
properly licensed images), and respect each website's terms of service. Do not
publish downloaded photos or ZIP files without the owner's permission.

## License

MIT. See [LICENSE](LICENSE).
