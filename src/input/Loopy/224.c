// Source: data/benchmarks/code2inv/109.c

void loopy_224(int a, int c, int m) {
    int j, k;

    j = 0;
    k = 0;

    while ( k < c) {
        if(m < a) {
            m = a;
        }
        k = k + 1;
    }

    if( c > 0 ) {
        {;
//@ assert( a <=  m);
}

    }
}