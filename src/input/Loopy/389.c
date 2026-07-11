// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark01_conjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x==1 && y==1;
*/
void loopy_389(int x, int y) {
  
  
  
  
  while (unknown_bool()) {
    x=x+y;
    y=x;
  }
  {;
//@ assert(y>=1);
}

  return;
}