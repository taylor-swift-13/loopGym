// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark16_conjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires 0 <= k && k <= 1 && i == 1;
*/
void loopy_403(int i, int k) {
  
  
  
  while (unknown_bool()) {
    i = i + 1;
    k = k - 1;
  }
  {;
//@ assert(1 <= i + k && i + k <= 2 && i >= 1);
}

  return;
}