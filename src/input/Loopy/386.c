// Source: data/benchmarks/sv-benchmarks/loop-new/gauss_sum.c
extern int unknown_int(void);

/*@
  requires 1 <= n && n <= 1000;
*/
void loopy_386(int n, int i) {
    int sum;
    
    sum = 0;
    {
  i = 1;
  while (i <= n) {
    sum = sum + i;
    i++;
  }
}
    {;
//@ assert(2*sum == n*(n+1));
}

    return;
}