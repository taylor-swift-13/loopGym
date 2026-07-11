// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark53_polynomial.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x*y>=0;
*/
void loopy_438(int x, int y) {
  
  
  
  
  while (unknown_bool()) {
    if(x==0) {if (y>0) x++;
    else x--;} if(x>0) y++;
    else x--;
  }
  {;
//@ assert(x*y>=0);
}

  return;
}