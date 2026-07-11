// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark15_conjunctive.c
extern int unknown_int(void);
/*@
  requires low == 0 && mid >= 1 && high == 2*mid;
*/
void loopy_402(int low, int mid, int high) {
  
  
  
  
  while (mid > 0) {
    low = low + 1;
    high = high - 1;
    mid = mid - 1;
  }
  {;
//@ assert(low == high);
}

  return;
}