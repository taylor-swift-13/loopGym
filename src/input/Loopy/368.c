// Source: data/benchmarks/sv-benchmarks/loop-lit/afnp2014.c
extern int unknown_int(void);

void loopy_368(void) {
    int x = 1;
    int y = 0;
    while (y < 1000 && unknown_int()) {
        x = x + y;
        y = y + 1;
    }
    {;
//@ assert(x >= y);
}

    return;
}