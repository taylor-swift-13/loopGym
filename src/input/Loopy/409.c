// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark22_conjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x==1 && y==0;
*/
void loopy_409(int x, int y) {
  
  
  
  while (unknown_bool()) {
    x=x+y;
    y++;
  }
  {;
//@ assert(x >= y);
}

  return;
}