// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark02_linear.c
extern int unknown_int(void);
/*@
  requires l>0;
*/
void loopy_390(int n, int l) {
  
  int i = unknown_int();
  
  i = l;
  
  while (i < n) {
    i++;
  }
  {;
//@ assert(l>=1);
}

  return;
}