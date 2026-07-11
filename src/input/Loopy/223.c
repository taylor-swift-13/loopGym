// Source: data/benchmarks/code2inv/108.c

/*@
  requires a <= m;
*/
void loopy_223(int a, int c, int m) {
    int j, k;

    
    j = 0;
    k = 0;

    while ( k < c) {
        if(m < a) {
            m = a;
        }
        k = k + 1;
    }

    {;
//@ assert( a <=  m);
}

}