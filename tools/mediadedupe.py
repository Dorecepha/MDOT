import zipfile, sys, hashlib, struct, collections, os

def png_dims(b):
    if b[:8]==b'\x89PNG\r\n\x1a\n' and b[12:16]==b'IHDR':
        return struct.unpack('>II', b[16:24])
    return None

uniq={}          # hash -> (size, dims)
per_file={}
occurrences=collections.Counter()
for p in sys.argv[1:]:
    n=0; tot=0
    for i in zipfile.ZipFile(p).infolist():
        if not i.filename.startswith('xl/media'): continue
        b=zipfile.ZipFile(p).read(i.filename)
        h=hashlib.sha256(b).hexdigest()
        n+=1; tot+=len(b)
        occurrences[h]+=1
        if h not in uniq: uniq[h]=(len(b), png_dims(b))
    per_file[os.path.basename(p)]=(n,tot)

for k,(n,tot) in per_file.items():
    print(f"{k}: {n} embedded images, {tot/1e6:.1f} MB")
ut=sum(s for s,_ in uniq.values())
emb=sum(n for n,_ in per_file.values())
print(f"\nTOTAL embedded: {emb} images, {sum(t for _,t in per_file.values())/1e6:.1f} MB")
print(f"UNIQUE by content: {len(uniq)} images, {ut/1e6:.1f} MB")
print(f"=> duplication factor {emb/len(uniq):.1f}x, wasted {(sum(t for _,t in per_file.values())-ut)/1e6:.1f} MB")

print("\nmost-reused images:")
for h,c in occurrences.most_common(6):
    s,d=uniq[h]; print(f"  x{c:4d}  {s/1024:7.0f} KB  {d}")

print("\nunique image size buckets:")
buckets=collections.Counter()
for s,d in uniq.values():
    if s<20*1024: buckets['<20 KB']+=1
    elif s<100*1024: buckets['20-100 KB']+=1
    elif s<500*1024: buckets['100-500 KB']+=1
    else: buckets['>500 KB']+=1
for k in ['<20 KB','20-100 KB','100-500 KB','>500 KB']:
    if buckets[k]: print(f"  {k:12s} {buckets[k]:5d}")

dims=collections.Counter(d for _,d in uniq.values() if d)
print("\nmost common dimensions:")
for d,c in dims.most_common(8): print(f"  {d[0]}x{d[1]}  x{c}")
