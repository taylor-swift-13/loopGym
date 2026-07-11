// Source: data/benchmarks/code2inv/107.c

void loopy_222(int a, int m) {
    int j, k;

    j = 0;
    k = 0;

    while ( k < 1) {
        if(m < a) {
            m = a;
        }
        k = k + 1;
    }

    {;
//@ assert( a <= m);
}

}