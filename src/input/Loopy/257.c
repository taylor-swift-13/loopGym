// Source: data/benchmarks/code2inv/19.c
extern int unknown(void);

void loopy_257(int z1, int z2, int z3, int n)
{
    
    int x = 0;
    int m = 0;
    

    while (x < n) {
        if (unknown()) {
            m = x;
        }
        x = x + 1;
    }

    if(n > 0) {
       {;
//@ assert(m < n);
}

    }
}