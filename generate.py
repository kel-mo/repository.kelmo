#!/usr/bin/env python3
"""Build zips/ (add-on zips, addons.xml, sha256 files, index.html) for GitHub Pages.

Usage: ./generate.py [ADDON_SOURCE_DIR | ADDON_ZIP ...]
The in-repo repository.kelmo/ is always included. Add-ons already in zips/ stay listed.
"""
import hashlib
import html
import io
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'zips')
REPO_ADDON = os.path.join(HERE, 'repository.kelmo')
EXCLUDE_DIRS = {'.git', 'dist', '__pycache__', '.ruff_cache', '.claude', 'tests', '.github'}
EXCLUDE_FILES = {'build.py', '.gitignore', 'README.md'}
ASSETS = ('icon', 'fanart', 'banner', 'clearlogo', 'thumb', 'screenshot')
EPOCH = (1980, 1, 1, 0, 0, 0)


def addon_info(xml_bytes):
    root = ET.fromstring(xml_bytes)
    return root.get('id'), root.get('version'), root


def version_key(v):
    """Order like Kodi: numeric parts, '~' suffix sorts before the release."""
    base, _, tag = v.partition('~')
    return [int(n) for n in re.findall(r'\d+', base)], 0 if tag else 1, tag


def source_files(src):
    """git ls-files when src is a checkout root, else a directory walk."""
    try:
        top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=src,
                                      stderr=subprocess.DEVNULL).decode().strip()
        if os.path.samefile(top, src):
            out = subprocess.check_output(['git', 'ls-files', '-z'], cwd=src)
            found = [p for p in out.decode().split('\0') if p]
        else:
            found = None
    except (OSError, subprocess.CalledProcessError):
        found = None
    if found is None:
        found = []
        for base, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            found += [os.path.relpath(os.path.join(base, n), src) for n in files if not n.endswith('.pyc')]
    return sorted(p for p in found
                  if os.path.basename(p) not in EXCLUDE_FILES
                  and not EXCLUDE_DIRS.intersection(p.split('/')[:-1])
                  and os.path.isfile(os.path.join(src, p)))


def zip_source(src):
    with open(os.path.join(src, 'addon.xml'), 'rb') as f:
        aid, ver, _ = addon_info(f.read())
    dest = os.path.join(OUT, aid, '{}-{}.zip'.format(aid, ver))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in source_files(src):
            path = os.path.join(src, rel)
            info = zipfile.ZipInfo('{}/{}'.format(aid, rel), EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
            with open(path, 'rb') as f:
                z.writestr(info, f.read())
    write_if_changed(dest, buf.getvalue())
    return dest


def import_zip(path):
    with zipfile.ZipFile(path) as z:
        tops = {n.split('/', 1)[0] for n in z.namelist()}
        if len(tops) != 1:
            sys.exit('{}: expected one top-level folder, got {}'.format(path, sorted(tops)))
        top = tops.pop()
        aid, ver, _ = addon_info(z.read(top + '/addon.xml'))
    if aid != top:
        sys.exit('{}: top-level folder {} != add-on id {}'.format(path, top, aid))
    dest = os.path.join(OUT, aid, '{}-{}.zip'.format(aid, ver))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(path, 'rb') as f:
        write_if_changed(dest, f.read())
    return dest


def write_if_changed(path, data):
    try:
        with open(path, 'rb') as f:
            if f.read() == data:
                return
    except FileNotFoundError:
        pass
    with open(path, 'wb') as f:
        f.write(data)


def write_sha256(path, data):
    """sha256sum format; Kodi reads the first token."""
    line = '{}  {}\n'.format(hashlib.sha256(data).hexdigest(), os.path.basename(path))
    write_if_changed(path + '.sha256', line.encode())


def hash_zips():
    for base, _dirs, files in os.walk(OUT):
        for name in files:
            if name.endswith('.zip'):
                with open(os.path.join(base, name), 'rb') as f:
                    write_sha256(os.path.join(base, name), f.read())


def newest_zips():
    """Newest zip per add-on id present under zips/."""
    best = {}
    for aid in sorted(os.listdir(OUT)):
        d = os.path.join(OUT, aid)
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            m = re.fullmatch(re.escape(aid) + r'-(.+)\.zip', name)
            if m and (aid not in best or version_key(m.group(1)) > version_key(best[aid][0])):
                best[aid] = (m.group(1), os.path.join(d, name))
    return {aid: path for aid, (_, path) in sorted(best.items())}


def publish(aid, path):
    """Return the <addon> element text and copy its declared assets next to the zip."""
    with zipfile.ZipFile(path) as z:
        raw = z.read(aid + '/addon.xml')
        _, _, root = addon_info(raw)
        for meta in root.iter('extension'):
            if meta.get('point') != 'xbmc.addon.metadata':
                continue
            for el in meta.iter():
                if el.tag in ASSETS and el.text and el.text.strip():
                    rel = el.text.strip()
                    if '{}/{}'.format(aid, rel) not in z.namelist():
                        print('warning: {} asset {} missing from zip'.format(aid, rel), file=sys.stderr)
                        continue
                    dest = os.path.join(OUT, aid, *rel.split('/'))
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    write_if_changed(dest, z.read('{}/{}'.format(aid, rel)))
    text = raw.decode('utf-8-sig')
    text = re.sub(r'^\s*<\?xml[^>]*\?>', '', text).strip()
    return text


def index_html(title, entries):
    """Plain link list; link text equals href so Kodi's HTTP directory parser accepts it."""
    items = ''.join('<li><a href="{0}">{0}</a></li>\n'.format(html.escape(e)) for e in entries)
    return ('<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>{0}</title></head>\n'
            '<body><h1>{0}</h1>\n<ul>\n{1}</ul>\n</body></html>\n').format(html.escape(title), items)


def write_indexes(repo_zip):
    for base, dirs, files in os.walk(OUT):
        dirs.sort()
        rel = os.path.relpath(base, OUT)
        entries = ['{}/'.format(d) for d in dirs] + sorted(f for f in files if f != 'index.html')
        title = 'kel-mo Kodi add-on repository' + ('' if rel == '.' else ' - ' + rel)
        page = index_html(title, entries)
        if rel == '.' and repo_zip:
            link = os.path.relpath(repo_zip, OUT).replace(os.sep, '/')
            page = page.replace('<ul>', '<p>Install from zip: <a href="{0}">{1}</a></p>\n<ul>'.format(
                html.escape(link), html.escape(os.path.basename(link))), 1)
        write_if_changed(os.path.join(base, 'index.html'), page.encode('utf-8'))


def main():
    os.makedirs(OUT, exist_ok=True)
    for arg in [REPO_ADDON] + sys.argv[1:]:
        arg = os.path.abspath(arg)
        if os.path.isdir(arg):
            print(os.path.relpath(zip_source(arg), HERE))
        elif zipfile.is_zipfile(arg):
            print(os.path.relpath(import_zip(arg), HERE))
        else:
            sys.exit('{}: not an add-on directory or zip'.format(arg))
    newest = newest_zips()
    body = ''.join(publish(aid, path) + '\n' for aid, path in newest.items())
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' + body + '</addons>\n').encode('utf-8')
    ET.fromstring(xml)
    write_if_changed(os.path.join(OUT, 'addons.xml'), xml)
    write_sha256(os.path.join(OUT, 'addons.xml'), xml)
    hash_zips()
    write_indexes(newest.get('repository.kelmo'))
    for aid, path in newest.items():
        print('{} -> {}'.format(aid, os.path.basename(path)))


if __name__ == '__main__':
    main()
