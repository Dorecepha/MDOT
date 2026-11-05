import zipfile, sys, collections, os
p=sys.argv[1]
z=zipfile.ZipFile(p)
infos=z.infolist()
tot=sum(i.file_size for i in infos)
print(f"{os.path.basename(p)}: {len(infos)} entries, uncompressed {tot/1e6:.1f} MB, on-disk {os.path.getsize(p)/1e6:.1f} MB")
by=collections.Counter(); cnt=collections.Counter()
for i in infos:
    top=i.filename.split('/')[0] if '/' in i.filename else '(root)'
    if i.filename.startswith('xl/media'): top='xl/media'
    by[top]+=i.file_size; cnt[top]+=1
for k,v in by.most_common(12):
    print(f"  {k:24s} {cnt[k]:6d} files  {v/1e6:9.1f} MB")
ext=collections.Counter(); extsz=collections.Counter()
for i in infos:
    if i.filename.startswith('xl/media'):
        e=os.path.splitext(i.filename)[1].lower(); ext[e]+=1; extsz[e]+=i.file_size
if ext:
    print("  media by type:")
    for e,c in ext.most_common():
        print(f"    {e:8s} {c:6d} files  {extsz[e]/1e6:8.1f} MB  avg {extsz[e]/c/1024:8.0f} KB")
big=sorted((i for i in infos if i.filename.startswith('xl/media')), key=lambda i:-i.file_size)[:5]
if big:
    print("  largest media:")
    for i in big: print(f"    {i.filename:40s} {i.file_size/1e6:7.2f} MB")
