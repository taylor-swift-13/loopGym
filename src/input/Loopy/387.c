// Source: data/benchmarks/sv-benchmarks/loop-new/half.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires k <= LARGE_INT && k >= -LARGE_INT;
*/
void loopy_387(int k) {
    int i = 0;
    int n = 0;
    
    
    {
  i = 0;
  while (i < 2*k) {
    if (i % 2 == 0) {
                n ++;
            }
    i++;
  }
}
    {;
//@ assert(k < 0 || n == k);
}

    return;
}