// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/terminator_02_true-unreach-call_true-termination.i.annot.c
extern int unknown_int(void);
extern int unknown_bool(void);

/*@
  requires x<100;
  requires x>-100;
  requires z<100;
  requires z>-100;
*/
void loopy_75(int x, int y, int z)
{
    
    
    




    while(x<100 && 100<z)
    {
        int  tmp=unknown_bool();
        if(tmp){
            x++;
        } else {
            x--;
            z--;
        }
    }
    {;
//@ assert(x>=100 || z<=100);
}

    return;
}