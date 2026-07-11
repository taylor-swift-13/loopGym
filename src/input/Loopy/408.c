// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark21_disjunctive.c
extern int unknown_int(void);
/*@
  requires y>0 || x>0;
*/
void loopy_408(int x, int y) {
  
  
  
  while (1) {
    if (x+y>-2) {
      break;
    }
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