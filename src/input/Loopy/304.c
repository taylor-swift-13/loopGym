// Source: data/benchmarks/code2inv/67.c

void loopy_304(int n, int y) {
    
    int x = 1;

    while (x <= n) {
        y = n - x;
        x = x +1;
    }

    if (n > 0) {
        {;
//@ assert(y >= 0);
}

    }
}