// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum01.c
extern int unknown_int(void);

#define a (1)
void loopy_99(int i, int n) { 
  int sn=0;
  {
  i=1;
  while (i<=n) {
    sn = sn + a;
    i++;
  }
}
  {;
//@ assert(sn==n*a || sn == 0);
}

}