// Source: data/benchmarks/sv-benchmarks/loops/terminator_02-2.c
extern int unknown_int(void);
extern int unknown_bool(void);

/*@
  requires x>-100;
  requires x<200;
  requires z>100;
  requires z<200;
*/
void loopy_465(int x, int z)
{
    
    
    
    
    
    
    while(x<100 && z>100) 
    {
        int tmp=unknown_bool();
        if (tmp) {
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
