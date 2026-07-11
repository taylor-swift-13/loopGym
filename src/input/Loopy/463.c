// Source: data/benchmarks/sv-benchmarks/loops/sum03-2.c
extern unsigned int unknown_uint(void);
#define a (2)

void loopy_463(unsigned int loop1, unsigned int n1) { 
  unsigned int sn=0;
  
  unsigned int x=0;

  while(1){
    sn = sn + a;
    x++;
    {;
//@ assert(sn==x*a || sn == 0);
}

  }
}
