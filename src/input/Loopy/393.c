// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark05_conjunctive.c
extern int unknown_int(void);
/*@
  requires x>=0 && x<=y && y<n;
*/
void loopy_393(int x, int y, int n) {
  
  
  
  
  
  while (x<n) {
    x++;
    if (x>y) y++;
  }
  {;
//@ assert(y==n);
}

  return;
}