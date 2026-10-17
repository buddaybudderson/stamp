"""Every [N] marker must land on reference N. Prints mismatches; exit 1 if any."""
import re, sys
from html.parser import HTMLParser
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.ols=[]; s.num={}; s.marks=[]; s.cur=None; s.buf=''
    def handle_starttag(s, t, a):
        a=dict(a)
        if t=='ol': s.ols.append(int(a.get('start',1))-1)
        if t=='li' and s.ols:
            n=int(a['value']) if 'value' in a else s.ols[-1]+1
            s.ols[-1]=n
            if 'id' in a: s.num[a['id']]=n
        if t=='a' and a.get('href','').startswith('#'): s.cur=a['href'][1:]; s.buf=''
    def handle_endtag(s, t):
        if t=='ol' and s.ols: s.ols.pop()
        if t=='a' and s.cur is not None:
            m=re.fullmatch(r'\[(\d+)\]', s.buf.strip())
            if m: s.marks.append((s.cur,int(m.group(1))))
            s.cur=None
    def handle_data(s, d):
        if s.cur is not None: s.buf+=d
bad=0
for f in sys.argv[1:]:
    p=P(); p.feed(open(f,encoding='utf-8').read())
    for tid,n in p.marks:
        if tid not in p.num: print(f, f'[{n}] -> #{tid}: NO SUCH REFERENCE'); bad+=1
        elif p.num[tid]!=n: print(f, f'[{n}] -> #{tid} which is reference {p.num[tid]}'); bad+=1
    print(f, len(p.marks), 'markers,', len(p.num), 'references')
sys.exit(1 if bad else 0)
