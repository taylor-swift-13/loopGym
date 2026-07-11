// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-lit/cggmp2005_true-unreach-call_true-termination.c

void loopy_52(void) {
    int i, j;
    i = 1;
    j = 10;
    while (j >= i) {
        i = i + 2;
        j = -1 + j;
    }
    {;
//@ assert(j == 6);
}

    return;
}