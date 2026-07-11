// Source: data/benchmarks/accelerating_invariant_generation/svcomp/sum01_true.c
extern int unknown_int(void);

#define a (2)

void loopy_207(int i, int n) { 
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