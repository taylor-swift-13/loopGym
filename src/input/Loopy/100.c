// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum01.v.c
extern int unknown_int(void);

#define a (1)
void loopy_100(int i, int n, int v1, int v2, int v3) { 
  int sn=0;
  
  {
  i=1;
  while (i<=n) {
    sn = sn + a;
        v1 = unknown_int();
        v2 = unknown_int();
        v3 = unknown_int();
    i++;
  }
}
  {;
//@ assert(sn==n*a || sn == 0);
}

}