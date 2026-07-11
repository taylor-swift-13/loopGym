// Source: data/benchmarks/code2inv/17.c
extern int unknown(void);

void loopy_255(int n)
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