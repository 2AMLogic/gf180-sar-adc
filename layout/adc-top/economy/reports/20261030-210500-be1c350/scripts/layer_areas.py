import sys, klayout.db as db
ly=db.Layout(); ly.read(sys.argv[1])
tops={c.name:c for c in ly.each_cell()}
li=ly.layer_infos()
for name in ['ADC_CDAC_ARRAY_N','ADC_DECODE_BANK_N','ADC_TOP_SW','COMPARATOR','ADC_BLOCK']:
    c=tops[name]; print(name)
    for l in li:
        idx=ly.find_layer(l.layer,l.datatype)
        r=db.Region(c.begin_shapes_rec(idx)).merged()
        a=r.area()/1e6
        if a>0: print(f"   {l.layer}/{l.datatype} {a:10.1f}")
