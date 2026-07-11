// Source: data/benchmarks/accelerating_invariant_generation/svcomp/sum03_true.c
extern unsigned int unknown_uint(void);

#define a (2)

void loopy_208(unsigned int loop1, unsigned int n1) { 
  int sn=0;
  
  unsigned int x=0;

  while(1){
    sn = sn + a;
    x++;
    {;
//@ assert(sn==x*a || sn == 0);
}

  }
}
