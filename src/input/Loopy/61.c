// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-lit/jm2006_true-unreach-call_true-termination.c
extern int unknown_int(void);

/*@
  requires i >= 0 && j >= 0;
*/
void loopy_61(int i, int j) {
    
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