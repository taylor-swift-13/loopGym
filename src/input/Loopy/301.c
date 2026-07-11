// Source: data/benchmarks/code2inv/64.c

void loopy_301(int y) {
    int x = 1;
    

    while (x <= 10) {
        y = 10 - x;
        x = x +1;
    }

    {;
//@ assert(y < 10);
}

}