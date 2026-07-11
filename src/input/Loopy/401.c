// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark14_linear.c
extern int unknown_int(void);
/*@
  requires i>=0 && i<=200;
*/
void loopy_401(int i) {
  
  
  
  while (i>0) {
    i--;
  }
  {;
//@ assert(i>=0);
}

  return;
}