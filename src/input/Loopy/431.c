// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark46_disjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires y>0 || x>0 || z>0;
*/
void loopy_431(int x, int y, int z) {
  
  
  
  
  while (unknown_bool()) {
    if (x>0) {
      x++;
    }
    if (y>0) {
      y++;
    } else {
      z++;
    }
  }
  {;
//@ assert(x>0 || y>0 || z>0);
}

  return;
}