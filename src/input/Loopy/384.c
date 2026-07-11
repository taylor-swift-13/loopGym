// Source: data/benchmarks/sv-benchmarks/loop-new/count_by_k.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires 0 <= k && k <= 10;
*/
void loopy_384(int i, int k) {
    
    {
  i = 0;
  while (i < LARGE_INT*k) {
    i += k;
  }
}
    {;
//@ assert(i == LARGE_INT*k);
}

    return;
}