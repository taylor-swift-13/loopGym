// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark50_linear.c
extern int unknown_int(void);
/*@
  requires xa + ya > 0;
*/
void loopy_435(int xa, int ya) {
  
  
  
  while (xa > 0) {
    xa--;
    ya++;
  }
  {;
//@ assert(ya >= 0);
}

  return;
}