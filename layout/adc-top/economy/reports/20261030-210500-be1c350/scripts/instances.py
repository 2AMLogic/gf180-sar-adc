import sys, klayout.db as db
ly=db.Layout(); ly.read(sys.argv[1]); top=ly.cell('ADC_BLOCK')
print('top bbox',top.bbox().to_s())
for i in top.each_inst():
    b=i.bbox(); print(i.cell.name, round(b.left/1e3,3),round(b.bottom/1e3,3),round(b.right/1e3,3),round(b.top/1e3,3), 'area',round(b.width()*b.height()/1e6,1))
# shapes directly in top by layer (rings, straps, lanes)
for l in ly.layer_infos():
    idx=ly.find_layer(l.layer,l.datatype)
    r=db.Region(top.shapes(idx)); 
    if r.count(): print('top-direct',l.layer,l.datatype,r.count(),round(r.bbox().left/1e3,2),round(r.bbox().bottom/1e3,2),round(r.bbox().right/1e3,2),round(r.bbox().top/1e3,2), round(r.merged().area()/1e6,1))
