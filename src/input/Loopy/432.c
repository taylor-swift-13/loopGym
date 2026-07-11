// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark47_linear.c
extern int unknown_int(void);
/*@
  requires x<y;
*/
void loopy_432(int x, int y) {
  
  
  
  while (x<y) {
    if (x < 0) x = x + 7;
    else x = x + 10;
    if (y < 0) y = y - 10;
    else y = y + 3;
  }
  {;
//@ assert(x >= y && x <= y + 16);
}

  return;
}