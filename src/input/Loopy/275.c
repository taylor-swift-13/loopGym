// Source: data/benchmarks/code2inv/39.c
extern int unknown(void);

/*@
  requires n > 0;
*/
void loopy_275(int n) {
    
    int c = 0;
    

    while (unknown()) {
        if(c == n) {
            c = 1;
        }
        else {
            c = c + 1;
        }
    }

    if(c == n) {
        
        {;
//@ assert( c <= n);
}

    }
}