// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum03_safe.c
extern unsigned int unknown_uint(void);

void loopy_105(unsigned int loop1, unsigned int n1) { 
  int sn=0;
  
  unsigned int x=0;

  while(1){
    sn = sn + 1;
    x++;
    {;
//@ assert(sn==x*1 || sn == 0);
}

  }
}
