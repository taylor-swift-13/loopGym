// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark13_conjunctive.c
extern int unknown_int(void);
/*@
  requires i==0 && j==0;
*/
void loopy_400(int i, int j, int k) {
  
  
  
  
  
  while (i <= k) {
    i++;
    j=j+1;
  }
  {;
//@ assert(j==i);
}

  return;
}