// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark08_conjunctive.c
extern int unknown_int(void);
/*@
  requires n>=0 && sum==0 && i==0;
*/
void loopy_395(int n, int sum, int i) {
  
  
  
  
  
  while (i<n) {
    sum=sum+i;
    i++;
  }
  {;
//@ assert(sum>=0);
}

  return;
}