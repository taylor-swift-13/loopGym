// Source: data/benchmarks/sv-benchmarks/loop-lit/cggmp2005.c

void loopy_370(void) {
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