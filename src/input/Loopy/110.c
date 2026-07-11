// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum04n.v.c
extern int unknown_int(void);

#define a (1)

void loopy_110(int i, int SIZE, int v1, int v2, int v3) { 
  int sn=0;
  
  
  {
  i=1;
  while (i<=SIZE) {
    sn = sn + a;
        v1 = unknown_int();
        v2 = unknown_int();
        v3 = unknown_int();
    i++;
  }
}
  {;
//@ assert(sn==SIZE*a || sn == 0);
}

}
