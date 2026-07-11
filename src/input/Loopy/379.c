// Source: data/benchmarks/sv-benchmarks/loop-lit/jm2006.c
extern int unknown_int(void);

/*@
  requires i >= 0 && j >= 0;
*/
void loopy_379(int i, int j) {
    
    int x = i;
    int y = j;
    while(x != 0) {
        x--;
        y--;
    }

    if (i == j) {
        {;
//@ assert(y == 0);
}

    }
    return;
}