// Source: data/benchmarks/sv-benchmarks/loop-lit/bhmr2007.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires n >= 0 && n <= LARGE_INT;
*/
void loopy_369(int n) {
    int i, a, b;
    i = 0; a = 0; b = 0;
    
    while (i < n) {
        if (unknown_int()) {
            a = a + 1;
            b = b + 2;
        } else {
            a = a + 2;
            b = b + 1;
        }
        i = i + 1;
    }
    {;
//@ assert(a + b == 3*n);
}

    return;
}