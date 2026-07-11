// Source: data/benchmarks/sv-benchmarks/loops/terminator_03-2.c
extern int unknown_int(void);
#define LIMIT 1000000

/*@
  requires y <= LIMIT;
*/
void loopy_466(int x, int y) {
    
    
    

    if (y>0) {
        while(x<100) {
            x=x+y;
        }
    }

    {;
//@ assert(y<=0 || (y>0 && x>=100));
}

    return;
}
