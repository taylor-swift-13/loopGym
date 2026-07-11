// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/terminator_03_true-unreach-call_true-termination.i.annot.c
extern int unknown_int(void);

/*@
  requires y <= 1000000;
*/
void loopy_76(int x, int y){
    
    

    if(y>0){
        while(x<100){
            x=x+y;
        }
    }
    {;
//@ assert(y<=0 ||(y>0 && x>=100));
}

    return;
}