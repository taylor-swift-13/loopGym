// Source: data/benchmarks/code2inv/68.c

void loopy_305(int n, int y) {
    
    int x = 1;

    while (x <= n) {
        y = n - x;
        x = x +1;
    }

    if (n > 0) {
        
        {;
//@ assert(y <= n);
}

    }
}