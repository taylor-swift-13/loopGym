// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/sum03_true-unreach-call_false-termination.i.annot.c
extern unsigned int unknown_uint(void);

void loopy_73(unsigned int loop1, unsigned int n1){
  int sn=0;
  
  unsigned int x=0;
  while(x < 1000000){
    sn = sn +(2);
    x++;
    {;
//@ assert(sn==x*(2)|| sn == 0);
}

  }
}