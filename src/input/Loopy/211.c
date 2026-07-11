// Source: data/benchmarks/accelerating_invariant_generation/svcomp/trex03_true.c
extern unsigned int unknown_uint(void);
extern int unknown_bool(void);

/*@
  requires (c1 == 0 || c1 == 1);
  requires (c2 == 0 || c2 == 1);
*/
void loopy_211(unsigned int x1, unsigned int x2, unsigned int x3, int c1, int c2)
{
  
  unsigned int d1=1, d2=1, d3=1;
  
  
  while(x1>0 && x2>0 && x3>0)
  {
    if (c1) x1=x1-d1;
    else if (c2) x2=x2-d2;
    else x3=x3-d3;
    c1=unknown_bool();
    c2=unknown_bool();
  }

  {;
//@ assert(x1==0 || x2==0 || x3==0);
}

  return;
}
