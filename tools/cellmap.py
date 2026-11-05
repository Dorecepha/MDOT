import csv, sys
def a1(n):
    s=""
    n+=1
    while n: n,r=divmod(n-1,26); s=chr(65+r)+s
    return s
path=sys.argv[1]
maxrow=int(sys.argv[2]) if len(sys.argv)>2 else 10**9
with open(path, newline='', encoding='utf-8') as f:
    rows=list(csv.reader(f))
print(f"rows={len(rows)} cols={max((len(r) for r in rows), default=0)}")
for i,row in enumerate(rows[:maxrow],1):
    cells=[(a1(j),v.strip()) for j,v in enumerate(row) if v.strip()]
    if not cells: continue
    out=" | ".join(f"{c}={v[:70]!r}" for c,v in cells)
    print(f"R{i}: {out}")
