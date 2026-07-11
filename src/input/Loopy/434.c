// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark49_linear.c
extern int unknown_int(void);
/*@
  requires r > i + j;
*/
void loopy_434(int i, int j, int r) {
  
  
  
  
  while (i > 0) {
    i = i - 1;
    j = j + 1;
  }
  {;
//@ assert(r > i + j);
}

  return;
}