// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum04n.c
extern int unknown_int(void);

#define a (1)

void loopy_109(int i, int SIZE) { 
  int sn=0;
  
  {
  i=1;
  while (i<=SIZE) {
    sn = sn + a;
    i++;
  }
}
  {;
//@ assert(sn==SIZE*a || sn == 0);
}

}
