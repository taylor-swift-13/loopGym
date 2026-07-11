// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum01_safe.c
extern int unknown_int(void);

void loopy_101(int i, int n) { 
  int sn=0;
  {
  i=1;
  while (i<=n) {
    sn = sn + 1;
    i++;
  }
}
  {;
//@ assert(sn==n || sn == 0);
}

}