// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark45_disjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires y>0 || x>0;
*/
void loopy_430(int x, int y) {
  
  
  
  while (unknown_bool()) {
    if (x>0) {
      x++;
    } else {
      y++;
    }
  }
  {;
//@ assert(x>0 || y>0);
}

  return;
}