// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark11_linear.c
extern int unknown_int(void);
/*@
  requires x==0 && n>0;
*/
void loopy_398(int x, int n) {
  
  
  
  
  while (x<n) {
    x++;
  }
  {;
//@ assert(x==n);
}

  return;
}