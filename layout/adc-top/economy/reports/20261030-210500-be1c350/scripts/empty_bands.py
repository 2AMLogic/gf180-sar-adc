import sys, klayout.db as db
ly=db.Layout(); ly.read(sys.argv[1]); top=ly.cell('ADC_BLOCK')
u=db.Region()
for i in top.each_inst(): u.insert(i.bbox())
u.merge()
core=db.Region(db.Box(-10860,-12390,588490,178660))
empty=core-u
print('core',core.area()/1e6,'empty',empty.area()/1e6)
def band(name,x0,y0,x1,y1):
    r=empty & db.Region(db.Box(int(x0*1e3),int(y0*1e3),int(x1*1e3),int(y1*1e3)))
    a=r.area()/1e6; return name,a
rects=[
 ('R-A right of decode banks, y below core top of banks (x>478.4,y<56.56)',478.4,-13,589,56.56),
 ('R-B right column beside comparator/switch band (x>478.4,56.56<=y<=103.66), excl comparator',478.4,56.56,589,103.66),
 ('R-C above comparator (x>431.4, y>103.66)',431.4,103.66,589,179),
 ('R-D strip right of arrays between arrays and comparator/sw (x 431.4..478.4, y 56.56..103.66)',431.4,56.56,478.4,103.66),
 ('R-E x 431.4..478.4 y 55.3..56.56 and y 103.66.. handled', 0,0,0,0),
 ('R-F gaps between stack rows (x -10.86..478.4, y -12.39..61.6) not in R-A',-11,-13,478.4,61.6),
 ('R-G left margin x<0 (all y), arrays zone',-11,61.6,-6.4,179),
 ('R-H top margin above arrays y>175.6 x<431.4',-11,175.6,431.4,179),
]
tot=0
seen=db.Region()
for n,x0,y0,x1,y1 in rects:
    if x1==0: continue
    r=empty & db.Region(db.Box(int(x0*1e3),int(y0*1e3),int(x1*1e3),int(y1*1e3)))
    r2=r-seen; seen=seen+r2
    print(f'{r2.area()/1e6:10.1f}  {n}')
print('covered',seen.area()/1e6,'remainder',(empty-seen).area()/1e6)
for p in (empty-seen).each(): 
    if p.area()>500e6: print(' rem', p.bbox().to_s(), p.area()/1e6)
