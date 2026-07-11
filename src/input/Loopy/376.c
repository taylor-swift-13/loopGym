// Source: data/benchmarks/sv-benchmarks/loop-lit/gr2006.c

void loopy_376(void) {
    int x, y;
    x = 0;
    y = 0;
    while (1) {
        if (x < 50) {
            y++;
        } else {
            y--;
        }
        if (y < 0) break;
        x++;
    }
    {;
//@ assert(x == 100);
}

    return;
}