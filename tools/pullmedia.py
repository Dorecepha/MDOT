"""Extract named media members from a workbook into a directory.

Usage: python -I tools/pullmedia.py <workbook.xlsx> <outdir> <name.png> [name.png ...]
"""
import os
import sys
import zipfile


def main():
    path, outdir = sys.argv[1], sys.argv[2]
    wanted = set(sys.argv[3:])
    os.makedirs(outdir, exist_ok=True)
    z = zipfile.ZipFile(path)
    found = 0
    for info in z.infolist():
        if not info.filename.startswith('xl/media/'):
            continue
        base = info.filename.split('/')[-1]
        if wanted and base not in wanted:
            continue
        dest = os.path.join(outdir, base)
        with open(dest, 'wb') as fh:
            fh.write(z.read(info.filename))
        print("%-18s %7d bytes" % (base, info.file_size))
        found += 1
    print("extracted %d" % found)
    return 0


if __name__ == '__main__':
    sys.exit(main())
