// Source: data/benchmarks/code2inv/132.c
extern int unknown(void);

void loopy_250(int j, int c, int t) {
    int i = 0;
    

    while( unknown() ) {
        if(c > 48) {
            if (c < 57) {
                j = i + i;
                t = c - 48;
                i = j + t;
            }
        }
    } 
    {;
//@ assert(i >= 0);
}

}