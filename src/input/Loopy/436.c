// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark51_polynomial.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires (x>=0) && (x<=50);
*/
void loopy_436(int x) {
  
  
  
  while (unknown_bool()) {
    if (x>50) x++;
    if (x == 0) { x ++;
    } else x--;
  }
  {;
//@ assert((x>=0) && (x<=50));
}

  return;
}