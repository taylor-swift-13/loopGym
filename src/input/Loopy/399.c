// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark12_linear.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x!=y && y==t;
*/
void loopy_399(int x, int y, int t) {
  
  
  
  
  
  while (unknown_bool()) {
    if(x>0) y=y+x;
  }
  {;
//@ assert(y>=t);
}

  return;
}