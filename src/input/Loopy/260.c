// Source: data/benchmarks/code2inv/21.c
extern int unknown(void);

void loopy_260(int z1, int z2, int z3, int n)
{
    
    int x = 1;
    int m = 1;
    

    while (x < n) {
        if (unknown()) {
            m = x;
        }
        x = x + 1;
    }

    if(n > 1) {
       {;
//@ assert(m < n);
}

    }
}