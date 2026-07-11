// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum03.v.c
extern int unknown_int(void);
extern unsigned int unknown_uint(void);

#define a (1)

void loopy_104(unsigned int loop1, unsigned int n1, int v1, int v2, int v3) { 
  int sn=0;
  
  unsigned int x=0;
  

  while(1){
    sn = sn + a;
    x++;
    {;
//@ assert(sn==x*a || sn == 0);
}

    v1 = unknown_int();
    v2 = unknown_int();
    v3 = unknown_int();
  }
}
