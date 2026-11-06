"""Minimal dependency-free .xlsx reader.

Exposes exactly what the MDOT extractor needs: cell text at true row/column
coordinates, merged ranges, and embedded-image anchors. `pip` is unavailable in
this environment, so this leans on zipfile + ElementTree only.

Zip member paths are always POSIX, hence posixpath throughout.
"""
import hashlib
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

NS = {
    'm': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
}

_CELL_RE = re.compile(r'^([A-Z]+)(\d+)$')


def col_to_index(letters):
    """'A' -> 0, 'AV' -> 47"""
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def index_to_col(n):
    """0 -> 'A', 47 -> 'AV'"""
    s = ""
    n += 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def split_ref(ref):
    """'AV191' -> (190, 47) as 0-based (row, col)"""
    m = _CELL_RE.match(ref)
    if not m:
        return None
    return int(m.group(2)) - 1, col_to_index(m.group(1))


def _resolve(base_part, target):
    if target.startswith('/'):
        return target.lstrip('/')
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def _rels_path(part):
    return posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')


class Workbook:
    def __init__(self, path):
        self.path = path
        self.zip = zipfile.ZipFile(path)
        self._names = set(self.zip.namelist())
        self._shared = self._read_shared_strings()
        self.sheets = self._read_sheet_index()

    # ---------- setup ----------

    def _read_shared_strings(self):
        if 'xl/sharedStrings.xml' not in self._names:
            return []
        root = ET.fromstring(self.zip.read('xl/sharedStrings.xml'))
        out = []
        for si in root.findall('m:si', NS):
            # Either a single <t>, or rich text split across <r><t> runs.
            parts = [t.text or '' for t in si.iter('{%s}t' % NS['m'])]
            out.append(''.join(parts))
        return out

    def _read_sheet_index(self):
        wb = ET.fromstring(self.zip.read('xl/workbook.xml'))
        rels = ET.fromstring(self.zip.read('xl/_rels/workbook.xml.rels'))
        relmap = {r.get('Id'): r.get('Target') for r in rels}
        sheets = {}
        for s in wb.findall('.//m:sheet', NS):
            rid = s.get('{%s}id' % NS['r'])
            sheets[s.get('name')] = _resolve('xl/workbook.xml', relmap[rid])
        return sheets

    # ---------- reading ----------

    def cells(self, tab):
        """{(row, col): text} 0-based, empty cells omitted."""
        root = ET.fromstring(self.zip.read(self.sheets[tab]))
        out = {}
        for c in root.iter('{%s}c' % NS['m']):
            ref = c.get('r')
            pos = split_ref(ref) if ref else None
            if pos is None:
                continue
            t = c.get('t')
            if t == 's':
                v = c.find('m:v', NS)
                if v is None or v.text is None:
                    continue
                text = self._shared[int(v.text)]
            elif t == 'inlineStr':
                node = c.find('m:is', NS)
                text = ''.join(x.text or '' for x in node.iter('{%s}t' % NS['m'])) if node is not None else ''
            else:
                v = c.find('m:v', NS)
                text = v.text if v is not None and v.text is not None else ''
            text = (text or '').strip()
            if text:
                out[pos] = text
        return out

    def merges(self, tab):
        """[((r0,c0),(r1,c1))] 0-based inclusive."""
        root = ET.fromstring(self.zip.read(self.sheets[tab]))
        out = []
        for mc in root.findall('.//m:mergeCell', NS):
            ref = mc.get('ref')
            if ':' not in ref:
                continue
            a, b = ref.split(':', 1)
            pa, pb = split_ref(a), split_ref(b)
            if pa and pb:
                out.append((pa, pb))
        return out

    def formulas(self, tab):
        """{(row, col): formula text} 0-based.

        Cells holding `=IMAGE("url")` have no cached value, so `cells()`
        reports them as empty — the picture lives at the URL, not in the
        workbook. Reading formulas is the only way to see them.
        """
        root = ET.fromstring(self.zip.read(self.sheets[tab]))
        out = {}
        for c in root.iter('{%s}c' % NS['m']):
            f = c.find('m:f', NS)
            ref = c.get('r')
            if f is None or not f.text or not ref:
                continue
            pos = split_ref(ref)
            if pos:
                out[pos] = f.text
        return out

    def hyperlinks(self, tab):
        """{(row, col): url} 0-based. Covers both r:id links and inline refs."""
        sp = self.sheets[tab]
        root = ET.fromstring(self.zip.read(sp))
        nodes = root.findall('.//m:hyperlink', NS)
        if not nodes:
            return {}

        relmap = {}
        rp = _rels_path(sp)
        if rp in self._names:
            rels = ET.fromstring(self.zip.read(rp))
            relmap = {r.get('Id'): r.get('Target') for r in rels}

        out = {}
        for h in nodes:
            ref = h.get('ref') or ''
            target = h.get('{%s}id' % NS['r'])
            url = relmap.get(target) if target else h.get('location')
            if not url:
                continue
            first = ref.split(':', 1)[0]
            pos = split_ref(first)
            if pos:
                out[pos] = url
        return out

    def images(self, tab):
        """[{row, col, member, size, sha256}] for each anchored image, 0-based."""
        sp = self.sheets[tab]
        root = ET.fromstring(self.zip.read(sp))
        dr = root.find('.//m:drawing', NS)
        if dr is None:
            return []

        srels = ET.fromstring(self.zip.read(_rels_path(sp)))
        smap = {r.get('Id'): r.get('Target') for r in srels}
        dpath = _resolve(sp, smap[dr.get('{%s}id' % NS['r'])])

        drels = ET.fromstring(self.zip.read(_rels_path(dpath)))
        dmap = {r.get('Id'): _resolve(dpath, r.get('Target')) for r in drels}
        dx = ET.fromstring(self.zip.read(dpath))

        out = []
        for tag in ('twoCellAnchor', 'oneCellAnchor', 'absoluteAnchor'):
            for anc in dx.findall('xdr:' + tag, NS):
                frm = anc.find('xdr:from', NS)
                blip = anc.find('.//a:blip', NS)
                if frm is None or blip is None:
                    continue
                member = dmap.get(blip.get('{%s}embed' % NS['r']))
                if not member or member not in self._names:
                    continue
                blob = self.zip.read(member)
                out.append({
                    'row': int(frm.find('xdr:row', NS).text),
                    'col': int(frm.find('xdr:col', NS).text),
                    'member': member,
                    'size': len(blob),
                    'sha256': hashlib.sha256(blob).hexdigest(),
                })
        return out

    def read_member(self, member):
        return self.zip.read(member)
