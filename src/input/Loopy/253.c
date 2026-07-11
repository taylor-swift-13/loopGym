// Source: data/benchmarks/code2inv/15.c
extern int unknown(void);

void loopy_253(int n)
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