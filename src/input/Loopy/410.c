// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark23_conjunctive.c
extern int unknown_int(void);
/*@
  requires i==0 && j==0;
*/
void loopy_410(int i, int j) {
  
  
  
  
  while (i<100) {
    j+=2;
    i++;
  }
  {;
//@ assert(j==200);
}

  return;
}