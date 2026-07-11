// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark30_conjunctive.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires y == x;
*/
void loopy_416(int x, int y) {
  
  
  
  while (unknown_bool()) {
    x++;
    y++;
  }
  {;
//@ assert(x == y);
}

  return;
}