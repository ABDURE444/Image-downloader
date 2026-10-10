#!/usr/bin/env python3
"""
Website Photo Downloader
------------------------
Give it one or more web page URLs. It downloads the photos on those pages
(JPG, JPEG, PNG, WebP), removes duplicates, sorts them into folders by page,
writes a README.txt listing where each image came from, and zips everything.

Needs only Python 3 (standard library) and an internet connection.

Easiest way: open this file, put your page links in the URLS list near the
top, save, then run:   python website_photo_downloader.py

Other ways (these override the URLS list)
    python website_photo_downloader.py https://example.com https://example.com/about
    python website_photo_downloader.py -f pages.txt -o my_photos

Options
    -f, --file FILE      text file with one page URL per line
    -o, --output NAME    name for the ZIP / folder (default: <site>_photos)
    --min-kb N           ignore images smaller than N KB (default 15)
    --logos              also keep logos
    --same-site-only     only keep images hosted on the same domain as the page
    --keep-folder        keep the unzipped folder after the ZIP is made
"""
import argparse
import hashlib
import html as htmllib
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from urllib.parse import urljoin, urlparse, unquote

# =====================================================================
#  >>> PUT YOUR PAGE LINKS HERE <<<
#  Replace the PASTE_... lines with the full page addresses you want
#  photos from. One link per line, each in quotes, ending with a comma.
#  Add more lines if you need more pages. Delete lines you don't need.
#
#  Example:
#      "https://www.mysite.com/",
#      "https://www.mysite.com/about.html",
# =====================================================================
URLS = [
    "PASTE_PAGE_LINK_1_HERE",
    "PASTE_PAGE_LINK_2_HERE",
    "PASTE_PAGE_LINK_3_HERE",
    "PASTE_PAGE_LINK_4_HERE",
    "PASTE_PAGE_LINK_5_HERE",
]

# Optional: name of the ZIP file (without .zip). Leave "" to name it after the website.
ZIP_NAME = ""
# =====================================================================

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
}
IMG_EXT = r"(?:jpe?g|png|webp)"
IMG_TOKEN = re.compile(r"\.%s(?:\?.*)?$" % IMG_EXT, re.I)

ATTR_RE = re.compile(r"""[\w:-]+\s*=\s*["']([^"']+)["']""", re.I)
CSS_URL_RE = re.compile(r"""url\(\s*["']?([^"')]+?)["']?\s*\)""", re.I)
ABS_URL_RE = re.compile(
    r"""https?://[^"'()\s,<>\\]+?\.%s(?:\?[^"'()\s,<>\\]*)?(?=["')\s,<>\\]|$)""" % IMG_EXT, re.I)
CSS_LINK_RE = re.compile(r"""<link[^>]+rel=["']?stylesheet["']?[^>]*>""", re.I)
HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)

JUNK_NAME = re.compile(
    r"(sprite|icon|favicon|pixel|spacer|blank|loading|loader|placeholder|arrow|"
    r"button|badge|separator|divider|(^|[-_])line[-_]?\d*\.|emoji|1x1|transparent|"
    r"facebook|twitter|instagram|linkedin|youtube|whatsapp|paypal|visa|mastercard)",
    re.I)
TRACKER_HOSTS = ("google-analytics", "googletagmanager", "doubleclick", "facebook.com/tr",
                 "pixel.", "analytics.", "scorecardresearch", "adservice", "hotjar")


def fetch(url, binary=False, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def looks_like_image(data):
    return (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
            or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"))


def extract_urls(text, base_url):
    """Find image URLs in attributes (src, data-src, srcset, href...), CSS url(...), and raw text."""
    text = text.replace("\\/", "/")
    text = htmllib.unescape(text)
    found = {}

    def add(raw):
        raw = raw.strip().strip(",")
        if not raw or raw.startswith("data:"):
            return
        if IMG_TOKEN.search(raw):
            found.setdefault(urljoin(base_url, raw), True)

    for m in ATTR_RE.finditer(text):
        for token in re.split(r"\s+", m.group(1)):
            add(token)
    for m in CSS_URL_RE.finditer(text):
        add(m.group(1))
    for m in ABS_URL_RE.finditer(text):
        add(m.group(0))
    return list(found)


def site_domain(host):
    return host.lower().removeprefix("www.")


def is_photo(url, page_host, args):
    p = urlparse(url)
    name = os.path.basename(p.path)
    if JUNK_NAME.search(name):
        if not (args.logos and "logo" in name.lower()):
            return False
    if "logo" in name.lower() and not args.logos:
        return False
    low = url.lower()
    if any(t in low for t in TRACKER_HOSTS):
        return False
    if args.same_site_only and site_domain(p.netloc) != site_domain(page_host):
        return False
    return True


def collapse_key(url):
    """Same picture in different sizes -> same key."""
    p = urlparse(url)
    path = re.sub(r"_orig(?=\.)", "", p.path)
    path = re.sub(r"-\d{2,4}x\d{2,4}(?=\.)", "", path)          # WordPress resizes
    path = re.sub(r"_(?:small|medium|large|thumb|grande|compact|\d{2,4}x\d{0,4})(?=\.)", "", path)
    return p.netloc + path


def candidates(url):
    """Possible full-size versions first, then the URL as found."""
    p = urlparse(url)
    root, ext = os.path.splitext(p.path)
    out = []
    if not root.endswith("_orig"):
        out.append(p._replace(path=root + "_orig" + ext, query="").geturl())   # Weebly originals
    wp = re.sub(r"-\d{2,4}x\d{2,4}$", "", root)                                 # WordPress originals
    if wp != root:
        out.append(p._replace(path=wp + ext, query="").geturl())
    if p.query:
        out.append(p._replace(query="").geturl())                               # drop ?w=300 style resizing
    out.append(url)
    seen, uniq = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def page_slug(url):
    p = urlparse(url)
    seg = [s for s in p.path.split("/") if s]
    slug = os.path.splitext(seg[-1])[0] if seg else "home"
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", unquote(slug)).strip("-") or "page"
    return slug.lower()


def safe_name(name):
    name = unquote(name)
    name = re.sub(r"_orig(?=\.)", "", name)
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name)


def get_pages_from_user(args):
    urls = list(args.urls)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            urls += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    if not urls:
        # use the links written in the URLS list at the top of this file
        urls = [u.strip() for u in URLS
                if u.strip() and not u.strip().upper().startswith("PASTE_") and not u.strip().startswith("#")]
    if not urls:
        print("No links found in the URLS list at the top of the file.")
        print("Paste the page URLs now (one per line). Press Enter on an empty line when done:")
        while True:
            ln = input("> ").strip()
            if not ln:
                break
            urls.append(ln)
    fixed = []
    for u in urls:
        if not re.match(r"https?://", u, re.I):
            u = "https://" + u
        if u not in fixed:
            fixed.append(u)
    return fixed


def main():
    ap = argparse.ArgumentParser(description="Download all photos from web pages into a ZIP.")
    ap.add_argument("urls", nargs="*", help="page URLs")
    ap.add_argument("-f", "--file")
    ap.add_argument("-o", "--output")
    ap.add_argument("--min-kb", type=float, default=15)
    ap.add_argument("--logos", action="store_true")
    ap.add_argument("--same-site-only", action="store_true")
    ap.add_argument("--keep-folder", action="store_true")
    args = ap.parse_args()

    pages = get_pages_from_user(args)
    if not pages:
        sys.exit("No URLs given.")

    name = args.output or ZIP_NAME or (site_domain(urlparse(pages[0]).netloc).replace(".", "_") + "_photos")
    name = re.sub(r"\.zip$", "", name, flags=re.I)
    folder, zip_name = name, name + ".zip"
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

    min_bytes = int(args.min_kb * 1024)
    by_hash = {}                  # sha256 -> info
    failed_pages, failed_imgs = [], []
    used_names = set()

    for purl in pages:
        slug = page_slug(purl)
        host = urlparse(purl).netloc
        print("\nPage:", purl)
        try:
            html = fetch(purl)
        except Exception as e:
            print("  [!] could not open page:", e)
            failed_pages.append(f"{purl}  ({e})")
            continue

        text = html
        for tag in CSS_LINK_RE.findall(html):          # also scan linked stylesheets for background images
            m = HREF_RE.search(tag)
            if not m:
                continue
            css_url = urljoin(purl, htmllib.unescape(m.group(1)))
            try:
                text += "\n" + fetch(css_url, timeout=25)
            except Exception:
                pass

        urls = [u for u in extract_urls(text, purl) if is_photo(u, host, args)]
        groups = {}
        for u in urls:
            groups.setdefault(collapse_key(u), []).append(u)
        print(f"  {len(groups)} candidate image(s)")
        if not groups:
            continue
        os.makedirs(os.path.join(folder, slug), exist_ok=True)

        n = 0
        for key, variants in groups.items():
            data, used = None, None
            tried = []
            for v in variants:
                tried += candidates(v)
            for cand in dict.fromkeys(tried):
                try:
                    d = fetch(cand, binary=True)
                except Exception:
                    continue
                if looks_like_image(d) and len(d) >= min_bytes:
                    data, used = d, cand
                    break
            if data is None:
                failed_imgs.append(f"{variants[0]}  (page: {purl})")
                continue
            h = hashlib.sha256(data).hexdigest()
            if h in by_hash:
                by_hash[h]["sources"].append(purl)
                print("  duplicate skipped:", os.path.basename(urlparse(used).path))
                continue
            n += 1
            base = safe_name(os.path.basename(urlparse(used).path))
            fname = f"{slug}_{n:02d}_{base}"
            while fname in used_names:
                fname = "x_" + fname
            used_names.add(fname)
            rel = os.path.join(slug, fname)
            with open(os.path.join(folder, rel), "wb") as f:
                f.write(data)
            by_hash[h] = {"file": rel.replace("\\", "/"), "url": used, "sources": [purl], "kb": len(data) // 1024}
            print(f"  saved {rel}  ({len(data)//1024} KB)")

    with open(os.path.join(folder, "README.txt"), "w", encoding="utf-8") as f:
        f.write("Downloaded photos\n")
        f.write(f"Total unique images: {len(by_hash)}\n")
        f.write(f"Pages requested: {len(pages)}\n\n")
        for info in by_hash.values():
            f.write(info["file"] + f"  ({info['kb']} KB)\n")
            f.write("    image URL : " + info["url"] + "\n")
            for s in info["sources"]:
                f.write("    found on  : " + s + "\n")
        if failed_pages:
            f.write("\nPages that could not be opened:\n  " + "\n  ".join(failed_pages) + "\n")
        if failed_imgs:
            f.write("\nImages that could not be downloaded:\n  " + "\n  ".join(failed_imgs) + "\n")

    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, folder))

    if not args.keep_folder:
        shutil.rmtree(folder)

    size = os.path.getsize(zip_name)
    print("\n==============================================")
    print(f"Unique photos downloaded : {len(by_hash)}")
    print(f"Pages that failed        : {len(failed_pages)}")
    print(f"Images that failed       : {len(failed_imgs)}")
    print(f"ZIP file                 : {os.path.abspath(zip_name)}  ({size//1024} KB)")
    if not by_hash:
        print("\nNo photos were saved. Try --min-kb 1, check the URLs, or check your internet connection.")


if __name__ == "__main__":
    main()
