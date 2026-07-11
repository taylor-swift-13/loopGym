// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark41_conjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x == y && y == 0 && z==0;
*/
void loopy_427(int x, int y, int z) {
  
  
  
  
  while (unknown_bool()) {
    x++;y++;z-=2;
  }
  {;
//@ assert(x == y && x >= 0 && x+y+z==0);
}

  return;
}