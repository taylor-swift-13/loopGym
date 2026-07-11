// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark48_linear.c
extern int unknown_int(void);
/*@
  requires i<j && k> 0;
*/
void loopy_433(int i, int j, int k) {
  
  
  
  
  while (i<j) {
    k=k+1;i=i+1;
  }
  {;
//@ assert(k > j - i);
}

  return;
}