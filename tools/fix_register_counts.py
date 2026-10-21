"""Set the static register counts on docs/corrections/index.html to what site.js computes.

site.js counts the rows of #register's table whose second cell is a <td>, by that cell's text,
and shows the last row's date as data-count-first. Without JavaScript the numbers in the HTML
are what a reader sees, so they must match. Usage: python -I fix_register_counts.py <repo> [--row]
--row also adds a dated Correction row saying the counts were wrong (it is counted too).
"""
import re, sys, pathlib
from html.parser import HTMLParser

repo = pathlib.Path(sys.argv[1])
p = repo / "docs" / "corrections" / "index.html"
s = p.read_text(encoding="utf-8")


class Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_reg = self.in_table = False
        self.depth = 0          # section nesting inside #register
        self.row = None         # list of [tag, text] cells
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section":
            if self.in_reg:
                self.depth += 1
            elif a.get("id") == "register":
                self.in_reg, self.depth = True, 1
        if not self.in_reg:
            return
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.row is not None and tag in ("td", "th"):
            self.cell = [tag, ""]
            self.row.append(self.cell)

    def handle_endtag(self, tag):
        if not self.in_reg:
            return
        if tag in ("td", "th"):
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.in_table = False
        elif tag == "section":
            self.depth -= 1
            if self.depth == 0:
                self.in_reg = False

    def handle_data(self, d):
        if self.cell is not None:
            self.cell[1] += d


def counts(html):
    r = Rows()
    r.feed(html)
    rows = [x for x in r.rows if len(x) > 1 and x[1][0] == "td"]
    kinds = {}
    for x in rows:
        k = x[1][1].strip()
        kinds[k] = kinds.get(k, 0) + 1
    return kinds, rows[-1][0][1].strip()


before, _ = counts(s)

if "--row" in sys.argv:
    k0 = {k: re.search(r'data-count-kind="%s">(\d+)<' % k, s).group(1) for k in ("Correction", "Change")}
    row = ('<tr><td>Oct 21, 2026</td><td>Correction</td><td><a href="#register">The counts at the top of this register</a></td>'
           '<td>The two figures above the register read %s corrections and %s changes in the page itself, counts that had fallen behind '
           'as rows were added. A script on the page recounts the rows when it loads, so most readers saw the right numbers; anyone '
           'reading without JavaScript, and any copy of the page, saw the old ones. The figures in the page are now computed from the '
           'register by <code>tools/fix_register_counts.py</code>.</td><td>Corrected</td></tr>') % (k0["Correction"], k0["Change"])
    anchor = "<th>Status</th></tr>"
    assert s.count(anchor) == 1
    s = s.replace(anchor, anchor + row)

kinds, first = counts(s)
for k in ("Correction", "Change"):
    pat = r'(data-count-kind="%s">)(\d+)(<)' % k
    assert len(re.findall(pat, s)) == 1, k
    s = re.sub(pat, lambda m: m.group(1) + str(kinds[k]) + m.group(3), s)
fp = r'(data-count-first[^>]*>)([^<]*)(<)'
if re.search(fp, s):
    s = re.sub(fp, lambda m: m.group(1) + first + m.group(3), s)
p.write_text(s, encoding="utf-8", newline="")
print("before", before, "-> after", kinds, "first", first)
