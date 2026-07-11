// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark38_conjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x == y && y == 0;
*/
void loopy_424(int x, int y) {
  
  
  
  while (unknown_bool()) {
    x+=4;y++;
  }
  {;
//@ assert(x == 4*y && x >= 0);
}

  return;
}