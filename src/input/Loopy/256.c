// Source: data/benchmarks/code2inv/18.c
extern int unknown(void);

void loopy_256(int n)
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
//@ assert(m >= 1);
}

    }
}