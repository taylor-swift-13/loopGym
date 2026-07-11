// Source: data/benchmarks/sv-benchmarks/loop-lit/cggmp2005_variant.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires mid > 0 && mid <= LARGE_INT;
*/
void loopy_371(int mid) {
    int lo, hi;
    lo = 0;
    
    hi = 2*mid;
    
    while (mid > 0) {
        lo = lo + 1;
        hi = hi - 1;
        mid = mid - 1;
    }
    {;
//@ assert(lo == hi);
}

    return;
}