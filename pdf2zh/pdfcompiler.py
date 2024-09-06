def pdf_compile(file:str,objs:list,trailer):
    with open(file,'wb') as f:
        xrefs=[]
        f.write('%PDF-1.7\n'.encode())
        for obj in objs:
            xrefs.append(f.tell())
            f.write(obj)
        startxref=f.tell()
        f.write(f'xref\n0 {len(objs)+1}\n0000000000 65536 f\n'.encode())
        for id,xref in enumerate(xrefs):
            if objs[id]==b'':
                f.write(f'{xref:0>10d} 00001 f\n'.encode())
            else:
                f.write(f'{xref:0>10d} 00000 n\n'.encode())
        f.write(f"trailer<<\n/Root {trailer['Root'].objid} 0 R\n/Info {trailer['Info'].objid} 0 R\n/Size {trailer['Size']}>>\n".encode())
        f.write(f'startxref\n{startxref}\n'.encode())
        f.write('%%EOF\n'.encode())