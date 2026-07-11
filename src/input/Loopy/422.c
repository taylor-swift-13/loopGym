// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark36_conjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x == y && y == 0;
*/
void loopy_422(int x, int y) {
  
  
  
  while (unknown_bool()) {
    x++;y++;
  }
  {;
//@ assert(x == y && x >= 0);
}

  return;
}