// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum03.c
extern unsigned int unknown_uint(void);

#define a (1)

void loopy_103(unsigned int loop1, unsigned int n1) { 
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
