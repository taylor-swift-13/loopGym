// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark20_conjunctive.c
extern int unknown_int(void);
/*@
  requires i==0 && n>=0 && n<=100 && sum==0;
*/
void loopy_407(int i, int n, int sum) {
  
  
  
  
  
  while (i<n) {
    sum = sum + i;
    i++;
  }
  {;
//@ assert(sum>=0);
}

  return;
}