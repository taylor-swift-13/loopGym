// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/trex03_true-unreach-call.i.annot.c
extern unsigned int unknown_uint(void);
extern int unknown_bool(void);

void loopy_77(unsigned int x1, unsigned int x2, unsigned int x3, int c1, int c2)
{
  
  unsigned int d1=1, d2=1, d3=1;
  
  while(x1>0 && x2>0 && x3>0)
  {
    if(c1)x1=x1-d1;
    else if(c2)x2=x2-d2;
    else x3=x3-d3;
    c1=unknown_bool();
    c2=unknown_bool();
  }
  {;
//@ assert(x1==0 || x2==0 || x3==0);
}

  return;
}