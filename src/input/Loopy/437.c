// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark52_polynomial.c
extern int unknown_int(void);
/*@
  requires i < 10 && i > -10;
*/
void loopy_437(int i) {
  
  
  while (i * i < 100) {
    i = i + 1;
  }
  {;
//@ assert(i == 10);
}

  return;
}